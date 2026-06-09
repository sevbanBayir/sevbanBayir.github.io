---
layout: post
title: "ConcurrentHashMap vs Race Conditions: The Read-Modify-Write Trap"
date: 2026-01-22 23:15:00 +0300
description: "Why simply swapping HashMap for ConcurrentHashMap doesn't fix race conditions in compound operations."
---

When dealing with concurrency in Kotlin (or Java), a common misconception is that using `ConcurrentHashMap` automatically makes all operations on the map thread-safe. While `ConcurrentHashMap` guarantees thread safety for individual method calls (like `put`, `get`, `remove`), it **does not** protect against race conditions in compound operations (Read-Modify-Write sequences).

## The Trap

Consider this synchronization demo:

```kotlin
fun synchronizationDemo() {
    val concurrentHashMap = ConcurrentHashMap<Int, Int>()

    GlobalScope.launch(Dispatchers.IO) {
        (1..100000).map {
            launch {
                val random = Random.nextInt(1, 9)
                
                // ❌ NON-ATOMIC OPERATION
                val currentCount = concurrentHashMap[random] ?: 0
                concurrentHashMap[random] = currentCount + 1
            }
        }.joinAll()
    }
}
```

### Why does this fail?

Even though `concurrentHashMap` is thread-safe, the logic above consists of three distinct steps:
1.  **Read**: `val currentCount = concurrentHashMap[random]`
2.  **Modify**: `val newCount = currentCount + 1`
3.  **Write**: `concurrentHashMap[random] = newCount`

If two coroutines read the same `currentCount` (say, 10) at the same time, they will both compute `11` and both write `11`. One increment is lost forever. This is a classic race condition.

## The Solution

To fix this, you must rely on atomic operations provided by `ConcurrentHashMap` itself, or use an `AtomicInteger` as the value.

### Option 1: `compute` (Recommended)

`compute` is atomic. The lambda is executed inside the map's lock (for that key), ensuring safe updates.

```kotlin
concurrentHashMap.compute(random) { _, count -> 
    (count ?: 0) + 1 
}
```

### Option 2: `merge`

`merge` is also atomic and arguably cleaner for simple counting scenarios.

```kotlin
concurrentHashMap.merge(random, 1, Int::plus)
```

### Option 3: Atomic Values

If you really want to keep the "get-increment" style, use `ConcurrentHashMap<Int, AtomicInteger>`.

```kotlin
val map = ConcurrentHashMap<Int, AtomicInteger>()
// ...
map.computeIfAbsent(random) { AtomicInteger(0) }.incrementAndGet()
```

### Option 4: Mutex (Coroutines)

If you are working within Kotlin Coroutines, you can use a `Mutex` (Mutual Exclusion) to create a critical section. This ensures only one coroutine can execute the block at a time.

```kotlin
val mutex = Mutex()
// ...
launch {
    mutex.withLock {
        // Safe critical section
        val currentCount = concurrentHashMap[random] ?: 0
        concurrentHashMap[random] = currentCount + 1
    }
}
```

*Note: While safe, this serialized access might be slower than `compute` or `merge` for high-contention scenarios because it locks the entire operation, not just the specific map bucket.*

## Summary

`ConcurrentHashMap` protects the **structure** of the map. It does not protect your **logic**. Always look for compound operations (get-check-put) and replace them with atomic alternatives like `compute`, `merge`, or `putIfAbsent`.
