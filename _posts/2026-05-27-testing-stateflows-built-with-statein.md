---
layout: post
title: "Testing StateFlows Built with stateIn: The Conflation Problem Nobody Warns You About"
date: 2026-05-27
categories: [android, testing]
tags: [kotlin, coroutines, stateflow, testing, turbine, android]
---

We were [told](https://proandroiddev.com/loading-initial-data-part-2-clear-all-your-doubts-0f621bfd06a0) to load initial data from network like this :

```kotlin
    private val _uiState = MutableStateFlow(CounterUiState())
    val uiState: StateFlow<CounterUiState> = _uiState
        .onStart { loadInitialCounter() }
        .stateIn(
            scope = sharingScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = _uiState.value
        )
```

But this is problematic when it comes to testing. Normally we would do something like this to define the top level state of the related screen and update it when necessary :

```kotlin
    private val _uiState = MutableStateFlow(CounterUiState())
    val uiState: StateFlow<CounterUiState> = _uiState.asStateFlow()
```

This is a pure backing property and does not have any side effects. The former one on the other hand, introduces an implicit boundary to a new coroutine and this new coroutine (i will call it the “relay coroutine” from now on) does not actually subscribe **directly** to the upstream flow which is the actual source of truth for our state emissions until the onStart function really finishes. This causes us to miss intermediate state updates to _uiState and effectively lower confidence in our tests. Yes, we don’t really need all the emissions all the time but on very specific and vital business logics we definitely do. 

In this article I will try to reduce (but not completely take it down unfortunately) these side effects and try to explain what actually happens under the hood. So, in some sense this should give you more confidence than not knowing anything and having to blindly assert on only the final state of the StateFlows.

## The Setup

This is a toy ViewModel from the reproduction repo that simulates frequent updates to state flows and how to test them.

First things first, even without all the drama above, testing stateflows requires special setup and attention as [Marton Braun](https://www.linkedin.com/in/zsmb13/) states in [his article](https://zsmb.co/conflating-stateflows/) very clearly: Collector of the stateflow must be faster than the producer. Which means using `UnconfinedDispatcher` when collecting in our tests and the viewmodels that sends updates must do this in a slower `StandardTestDispatcher`.

To be able to test this viewmodel:

```kotlin
class CounterViewModel() : ViewModel() {

    private val _uiState = MutableStateFlow(CounterUiState())
    val uiState: StateFlow<CounterUiState> = _uiState.asStateFlow()

    fun incrementAsync() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }   // ①
            _uiState.update { it.copy(isLoading = false) }  // ②
            _uiState.update { it.copy(isLoading = true) }   // ③
            delay(1000)
            _uiState.update { it.copy(count = it.count + 1, isLoading = false) } // ④
        }
    }
}
```

Our minimal setup would be like this :

- Set main dispatcher with a JUnit5 extension:

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class MainDispatcherExtension(
    val testDispatcher: TestDispatcher = StandardTestDispatcher()
) : BeforeEachCallback, AfterEachCallback {

    override fun beforeEach(context: ExtensionContext?) {
        Dispatchers.setMain(testDispatcher)
    }

    override fun afterEach(context: ExtensionContext?) {
        Dispatchers.resetMain()
    }
}
```

Since this will be the producer of the updates (viewmodelScope == Dispatchers.Main.immediate) we set it to StandardTestDispatcher().

- Collect with a faster coroutine context which is the Turbine in our case. Turbine uses `UnconfinedTestDispatcher` when it is called from inside a runTest block:

With these setups this test case passes no matter how frequently you update your `StateFlow` :

```kotlin
@Test
fun `Case 4 - asStateFlow - all 5 emissions observed`() = runTest {
    val viewModel = CounterViewModel()

    viewModel.uiState.test {
        assertThat(awaitItem()).isEqualTo(CounterUiState())

        viewModel.incrementAsync()

        assertThat(awaitItem().isLoading).isTrue()
        assertThat(awaitItem().isLoading).isFalse()
        assertThat(awaitItem().isLoading).isTrue()

        val done = awaitItem()
        assertThat(done.isLoading).isFalse()
        assertThat(done.count).isEqualTo(1)
    }
}
```

Which means you can catch every single emission as you expected and which is normal and intuitive.
At this point if you don’t need any fine-grained assertion you’d simply go assert on .value property of the StateFlow and if you do need fine-grained access to emission they are simply there deterministically.

## When Things Get Messed Up

### The Setup

Here is the same viewmodel but let’s go try to load initial data as [Skydoves’ article](https://proandroiddev.com/loading-initial-data-part-2-clear-all-your-doubts-0f621bfd06a0) suggests:

```kotlin
class CounterViewModel() : ViewModel() {

    private val _uiState = MutableStateFlow(CounterUiState())
    val uiState: StateFlow<CounterUiState> = _uiState
        .onStart { loadInitialCounter() }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = _uiState.value
        )

    fun incrementAsync() {
        // ... Same content as before.
    }

    suspend fun loadInitialCounter() {
        delay(1.seconds)
        // loads initial data
        // Be careful, we are not yet making updates here
    }
}
```

### The Truth

With this simple change, the number of emissions you can catch is now down to 2. You can only catch the first and last emissions.
Here you can see the missing ones:

| # | Emission | Observed? |
| --- | --- | --- |
| 0 | `(count=0, isLoading=false)` | ✅ |
| 1 | `(count=0, isLoading=true)` | ❌ |
| 2 | `(count=0, isLoading=false)` | ❌ |
| 3 | `(count=0, isLoading=true)` | ❌ |
| 4 | `(count=1, isLoading=false)` | ✅ |

## Understanding Why

Before getting into what `stateIn` specifically does, it is worth understanding the two test dispatchers involved, because the entire problem comes down to their interaction.

### `StandardTestDispatcher` the lazy queue

Every coroutine continuation is placed into a FIFO task queue. Nothing runs until the scheduler is explicitly advanced — by a `delay()`, `advanceUntilIdle()`, or a suspension in the test body. A coroutine runs completely uninterrupted until it hits a suspension point; the scheduler cannot insert anything between two non-suspending lines. Putting it another way : it needs some work to be suspended to run its queued works to be ran.

This faithfully models how `Dispatchers.Main` works on Android in production: the Looper processes one message at a time, cooperatively. `launch { }` posts a message — it does not preempt what is running. In other words, a running coroutine must yield or suspend before queued works can be executed.

### `UnconfinedTestDispatcher` the eager inline runner

When a coroutine is resumed, it runs **immediately and inline** on the current thread before returning to the caller. There is no queue. This is a test-only construct with no direct real-world analogue — it exists purely to make a collector faster than its producer.

### The fundamental rule

As I stated at the beginning of this article :

> **The only way to avoid `StateFlow` conflation in tests is: collector on `UnconfinedTestDispatcher`, producer on slower `StandardTestDispatcher`.**
> 

| Producer | Collector | Result |
| --- | --- | --- |
| Standard | Unconfined | ✅ No conflation |
| Standard | Standard | ❌ Conflation |
| Unconfined | Unconfined | ❌ Conflation |
| Unconfined | Standard | ❌ Conflation |

This is because `StateFlow` uses a **binary slot** (not a queue) per collector:
- `NONE` — collector is sleeping
- `PENDING` — collector has been woken up

If the slot is already `PENDING` when a new value is written, the new value silently overwrites the old one. The slot is a flag, not a counter — it has no memory of intermediate values.

Under `StandardTestDispatcher`, the slot stays PENDING across multiple rapid updates because the collector is queued and cannot run between non-suspending lines. Under `UnconfinedTestDispatcher`, the collector runs inline after every update, resetting the slot to NONE before the next update fires.

## What `stateIn` Actually Does

This is the part that is not obvious from the documentation.

When you write:

```kotlin
val uiState = _uiState
    .onStart { loadInitialCounter() }
    .stateIn(scope = someScope, ...)
```

`stateIn` silently creates a **relay coroutine** inside `someScope`. Its job is to collect from `_uiState.onStart { ... }` and forward every value into an internal `sharedState: MutableStateFlow<T>`. Collectors like Turbine subscribe to `sharedState` not to `_uiState` directly.

```
_uiState  ←── incrementAsync
    ↓
[relay coroutine]  ← inserted by stateIn
    ↓
sharedState (internal)
    ↓
[Turbine]
```

With `asStateFlow()` there is no relay coroutine:

```
_uiState  ←── incrementAsync
    ↓
[Turbine]
```

The relay introduces an **extra conflation point**. Even if Turbine is Unconfined, it never sees an intermediate value that the relay already conflated before forwarding to `sharedState`.

## The Root Cause: Who Is Actually Collecting `_uiState`?

In the original setup, `stateIn` is passed `viewModelScope`:

```
incrementAsync   → viewModelScope → StdTestDispatcher (via setMain)  ← producer
relay            → viewModelScope → StdTestDispatcher (via setMain)  ← collector
Turbine          → internally     → UnconfinedTestDispatcher
```

Both `incrementAsync` and the relay share `viewModelScope`. Both are on `StandardTestDispatcher`. So from `_uiState`’s perspective:

- Producer: Standard
- Collector (relay): Standard
- **Losing combination**

Turbine being Unconfined is irrelevant — the intermediate values are already conflated before they ever reach `sharedState`.

### Why the three synchronous updates are always collapsed

Updates `①②③` have no suspension points between them:

```kotlin
_uiState.update { it.copy(isLoading = true) }   // ①
_uiState.update { it.copy(isLoading = false) }  // ②  ← no suspension
_uiState.update { it.copy(isLoading = true) }   // ③  ← no suspension
delay(1000)                                      // ← first suspension point
```

When ① fires, the relay’s slot flips to PENDING and the relay is queued. When ② fires, the slot is already PENDING — the value is overwritten, nothing new is enqueued. Same for ③. When `delay(1000)` finally suspends `incrementAsync`, the relay runs for the first time and reads `_uiState.value` — which is only ③’s value. Updates ① and ② are gone.

## Attempts to Fix It

### Attempt 1: `setMain(UnconfinedTestDispatcher)`

If the relay is Unconfined, it should dispatch inline between each update, right?

The problem: both the relay and `incrementAsync` share `viewModelScope`. Changing `setMain` to `UnconfinedTestDispatcher` makes **both** Unconfined. When `incrementAsync` (Unconfined) holds the thread during `①②③`, the relay (also Unconfined) cannot preempt it. **Unconfined/Unconfined is a losing combination.**

### Attempt 2: Scope Injection

Give `stateIn` its own scope so the relay lives separately from `incrementAsync`:

```kotlin
class CounterViewModel(
    sharingDispatcher: CoroutineDispatcher = Dispatchers.Main.immediate
) : ViewModel() {

    private val sharingScope = CoroutineScope(
        viewModelScope.coroutineContext + sharingDispatcher  // inherits Job for lifecycle
    )

    val uiState = _uiState
        .onStart { loadInitialCounter() }
        .stateIn(scope = sharingScope, ...)
}
```

In tests:

```kotlin
viewModel = CounterViewModel(
    sharingDispatcher = UnconfinedTestDispatcher(
        mainDispatcherExtension.testDispatcher.scheduler
    )
)
```

**Result: 3 of 5 emissions observed** — regardless of whether `Standard` or `Unconfined` was passed. The dispatcher injected did not matter.

### Why the dispatcher didn’t matter here

`loadInitialCounter()` contains `delay(1.seconds)`. This means:

> The relay is parked inside `onStart` when `incrementAsync` fires `①②③`. It has not yet subscribed to `_uiState`. The relay’s dispatcher is irrelevant during that window — it isn’t listening.
> 

When `onStart`’s `delay` completes (T=1s), the relay finally subscribes to `_uiState` and receives a single snapshot of the current value - which is ③’s residue. Whether the relay is Standard or Unconfined, it sees only one value because `①②③` already happened before it subscribed.

### The Crucial Exception: Synchronous `onStart`

What if your mock setup in tests is completely synchronous (e.g., your `onStart` block has no suspension points because your repository mock returns data immediately)? 

Suddenly, **the dispatcher you inject matters completely**. 

When `onStart` has no suspension, the relay coroutine completes its initialization and subscribes to `_uiState` **synchronously at T=0**, *before* `incrementAsync` ever fires. 

Because it is subscribed when the rapid updates fire, the Unconfined/Standard dispatcher rules apply:
* **With Standard sharingDispatcher:** Standard producer + Standard collector = **3 of 5 emissions** (conflation occurs at the relay).
* **With Unconfined sharingDispatcher:** Standard producer + Unconfined collector = **5 of 5 emissions** (perfect, non-conflated observability!).

If your test mocks are synchronous (which is common and highly recommended where possible), **Scope Injection + UnconfinedTestDispatcher is a perfect, non-invasive cure.**

### Attempt 3: `yield()` between updates

Add suspension points between `①②③` so the relay has a window:

```kotlin
_uiState.update { it.copy(isLoading = true) }
yield()
_uiState.update { it.copy(isLoading = false) }
yield()
_uiState.update { it.copy(isLoading = true) }
```

**Result: still failed.** `yield()` reshuffles the scheduler queue but does not advance virtual time. The order in which the scheduler picks between `viewModelScope`’s queue and `sharingScope`’s queue is not guaranteed. `incrementAsync` may be picked again before the relay.

### Attempt 4: `delay()` between updates

```kotlin
_uiState.update { it.copy(isLoading = true) }
delay(x)
_uiState.update { it.copy(isLoading = false) }
delay(x)
_uiState.update { it.copy(isLoading = true) }
```

**Result: all 5 caught.** `delay()` parks `incrementAsync` at a future virtual timestamp, removing it from the current runnable queue entirely. The relay has an exclusive window to drain.

| Suspension | Virtual time advances | Guarantees relay runs before next update |
| --- | --- | --- |
| `yield()` | ❌ | ❌ — reshuffles queue, order not guaranteed |
| `delay()` | ✅ | ✅ — parks producer, relay has exclusive window |

These two last attempts will never make in to production since we must strictly avoid changing prod code in favor of testing. Plus, they may not be ever needed.

## A Subtle Side Effect: `onStart` Mutation and `initialValue`

When `loadInitialCounter()` mutates `_uiState` (e.g., increments the count) and contains a suspension point, there is an important timing effect on what Turbine observes.

`stateIn`’s `initialValue` is captured at **ViewModel construction time**. It does not update as `_uiState` changes. So the subscription sequence is:

```
Turbine subscribes
  → stateIn emits initialValue=(count=0) into sharedState immediately
  → relay enters onStart → hits delay → PARKS
  → sharedState is still (count=0)

test calls awaitItem()
  → reads (count=0) ← always, because relay is parked

virtual time advances → onStart resumes → increment() fires
  → _uiState=(count=1)
  → relay subscribes → reads snapshot → forwards (count=1) to sharedState
  → next awaitItem() returns (count=1)
```

**This behavior is strictly deterministic - not flaky:**

| `onStart` before mutation | First `awaitItem()` | Second `awaitItem()` (after advancing time) |
| --- | --- | --- |
| Has suspension point | `initialValue` (non-mutated) | Mutated value |
| No suspension point | Mutated value (overwrites `initialValue` before first read) | Next emission from producer |

The suspension point is a hard guarantee. The relay physically cannot write to `sharedState` until virtual time is advanced. `awaitItem()` always wins because the relay is not racing — it is stopped.

Here you can see how complex the things are being, in every step of this onStart approach. There are so much going on and you have to keep these in mind if you want both the confident tests and the behavior onStart + WhileSubscribed provides.

## The Final Setup That Works

```kotlin
// Production ViewModel
class CounterViewModel(
    sharingDispatcher: CoroutineDispatcher = Dispatchers.Main.immediate
) : ViewModel() {

    private val sharingScope = CoroutineScope(
        viewModelScope.coroutineContext + sharingDispatcher
    )

    private val _uiState = MutableStateFlow(CounterUiState())
    val uiState: StateFlow<CounterUiState> = _uiState
        .onStart { loadInitialCounter() }
        .stateIn(
            scope = sharingScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = _uiState.value
        )
}

// Test setup
@OptIn(ExperimentalCoroutinesApi::class)
class CounterViewModelTest {

    @JvmField
    @RegisterExtension
    val mainDispatcherExtension = MainDispatcherExtension()

    @BeforeEach
    fun setup() {
        viewModel = CounterViewModel(
            sharingDispatcher = UnconfinedTestDispatcher(
                mainDispatcherExtension.testDispatcher.scheduler
            )
        )
    }
}
```

### Why Sharing the Scheduler is a Hard Requirement

Notice that we did not just write `UnconfinedTestDispatcher()`. Instead, we explicitly passed the scheduler:

```kotlin
UnconfinedTestDispatcher(mainDispatcherExtension.testDispatcher.scheduler)
```

**Do not omit this scheduler!** If you instantiate `UnconfinedTestDispatcher()` without arguments in your setup, it will create a fresh, decoupled `TestCoroutineScheduler`. The virtual clocks of your `viewModelScope` (running on Main's `StandardTestDispatcher` scheduler) and the `sharingScope` will diverge. Calling `delay()` or `advanceUntilIdle()` in your test will advance Main's clock while leaving the `sharingScope` frozen in time, causing tests to hang indefinitely or fail silently.

With `delay()` between updates in production code and `Unconfined` relay in tests, all 5 emissions are observable. Without `delay()` between updates and with a suspended `onStart`, only 3 are observable — which may be acceptable depending on what you actually need to assert.

## Summary: Which Solution Should You Choose?

When deciding how to handle state collection in your codebase, consider this decision matrix:

1. **Option A: `asStateFlow()` (Highly Recommended)**
   * *When to use:* If you can easily move your data-loading logic from `.onStart` into an `init { viewModelScope.launch { ... } }` block.
   * *Why:* It eliminates the relay coroutine entirely. Turbine gets direct, 100% observable access, and no special dispatcher injection or custom testing scopes are required.

2. **Option B: Scope Injection + Unconfined Test Dispatcher**
   * *When to use:* If you must keep `.onStart` (e.g., for lazy subscription triggers or reactive restarts).
   * *How:* Inject an `UnconfinedTestDispatcher` sharing the main test scheduler into your custom `sharingScope` in tests.
   * *Observability:* You'll get **5 of 5 emissions** if your mock setup runs synchronously in tests, and **3 of 5** (conflating rapid updates) if your `onStart` suspends.

## What I Learned

As you can see, the advised initial data loading approach by skydoves and google itself contains much more quirks in it when you want high confidence and deterministic tests. So, you must mind your decision thoroughly when adopting onStart + WhileSubscribed approach. You can get the source code for all cases i demonstrated here and more on [this reproduction repo](https://github.com/sevbanBayir/TestingExperiment).

## References

- [The conflation problem of testing StateFlows — Márton Braun (zsmb.co)](https://zsmb.co/conflating-stateflows/)
- [Testing Kotlin coroutines on Android — Android Developers](https://developer.android.com/kotlin/coroutines/test)
- [Testing StateFlows — Android Developers](https://developer.android.com/kotlin/flow/test#stateflows)
- [Turbine — CashApp](https://github.com/cashapp/turbine)
