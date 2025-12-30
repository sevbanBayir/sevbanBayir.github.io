---
layout: post
title: "Uber RIBs: A Simple & Modern Prototype with Jetpack Compose"
date: 2025-12-30
categories: [Android, Architecture]
tags: [ribs, jetpack-compose, android, uber, architecture]
toc: true
---

## Introduction

If you've worked on large-scale mobile applications, you've likely encountered the challenge of managing complexity as your codebase grows. Uber's **RIBs** (Router, Interactor, Builder) architecture provides an elegant solution to this problem.

In this post, I'll walk you through implementing a modern RIBs prototype using **Jetpack Compose**—combining Uber's battle-tested architecture with Android's declarative UI framework.

## What is RIBs?

RIBs is a cross-platform mobile architecture framework developed by Uber. The name stands for:

- **Router**: Handles navigation logic and attaches/detaches child RIBs
- **Interactor**: Contains business logic and manages the RIB's lifecycle
- **Builder**: Constructs all RIB components with proper dependency injection

### Why RIBs?

Traditional architectures like MVVM or MVP work well for smaller apps, but they can become unwieldy at scale. RIBs offers several advantages:

1. **Business logic-driven architecture** - The app tree is structured around business logic, not UI
2. **Deep hierarchy support** - Perfect for apps with complex navigation flows
3. **Testability** - Each component is highly testable in isolation
4. **Cross-platform consistency** - Shared architecture patterns between iOS and Android

## The RIB Structure

A typical RIB consists of these components:

```
┌─────────────────────────────────────┐
│              Builder                │
│   (Creates all RIB components)      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│             Router                  │
│   (Navigation & child management)   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│           Interactor                │
│   (Business logic & lifecycle)      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│           View/Presenter            │
│   (UI - Jetpack Compose!)           │
└─────────────────────────────────────┘
```

## Implementing RIBs with Jetpack Compose

Let's build a simple authentication flow using RIBs and Compose.

### Base Components

First, define the base interfaces:

```kotlin
interface Interactor {
    fun didBecomeActive()
    fun willResignActive()
}

interface Router<I : Interactor> {
    val interactor: I
    fun didLoad()
    fun attachChild(router: Router<*>)
    fun detachChild(router: Router<*>)
}

interface Builder<T> {
    fun build(): T
}
```

### Login RIB Implementation

**LoginInteractor.kt**
```kotlin
class LoginInteractor(
    private val listener: Listener
) : Interactor {
    
    interface Listener {
        fun onLoginSuccess(userId: String)
    }
    
    private val _state = MutableStateFlow(LoginState())
    val state: StateFlow<LoginState> = _state.asStateFlow()
    
    override fun didBecomeActive() {
        // Initialize any subscriptions or data loading
    }
    
    override fun willResignActive() {
        // Clean up subscriptions
    }
    
    fun onEmailChanged(email: String) {
        _state.update { it.copy(email = email) }
    }
    
    fun onPasswordChanged(password: String) {
        _state.update { it.copy(password = password) }
    }
    
    fun onLoginClicked() {
        _state.update { it.copy(isLoading = true) }
        // Simulate authentication
        viewModelScope.launch {
            delay(1000)
            listener.onLoginSuccess(_state.value.email)
        }
    }
}

data class LoginState(
    val email: String = "",
    val password: String = "",
    val isLoading: Boolean = false,
    val error: String? = null
)
```

**LoginRouter.kt**
```kotlin
class LoginRouter(
    override val interactor: LoginInteractor
) : Router<LoginInteractor> {
    
    private val children = mutableListOf<Router<*>>()
    
    override fun didLoad() {
        interactor.didBecomeActive()
    }
    
    override fun attachChild(router: Router<*>) {
        children.add(router)
        router.didLoad()
    }
    
    override fun detachChild(router: Router<*>) {
        router.interactor.willResignActive()
        children.remove(router)
    }
}
```

**LoginBuilder.kt**
```kotlin
class LoginBuilder(
    private val dependency: LoginDependency
) : Builder<LoginRouter> {
    
    interface LoginDependency {
        val loginListener: LoginInteractor.Listener
    }
    
    override fun build(): LoginRouter {
        val interactor = LoginInteractor(dependency.loginListener)
        return LoginRouter(interactor)
    }
}
```

### The Compose View

**LoginScreen.kt**
```kotlin
@Composable
fun LoginScreen(
    interactor: LoginInteractor
) {
    val state by interactor.state.collectAsState()
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "Welcome Back",
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold
        )
        
        Spacer(modifier = Modifier.height(32.dp))
        
        OutlinedTextField(
            value = state.email,
            onValueChange = interactor::onEmailChanged,
            label = { Text("Email") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        OutlinedTextField(
            value = state.password,
            onValueChange = interactor::onPasswordChanged,
            label = { Text("Password") },
            modifier = Modifier.fillMaxWidth(),
            visualTransformation = PasswordVisualTransformation(),
            singleLine = true
        )
        
        Spacer(modifier = Modifier.height(24.dp))
        
        Button(
            onClick = interactor::onLoginClicked,
            modifier = Modifier
                .fillMaxWidth()
                .height(50.dp),
            enabled = !state.isLoading
        ) {
            if (state.isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = MaterialTheme.colorScheme.onPrimary
                )
            } else {
                Text("Sign In")
            }
        }
        
        state.error?.let { error ->
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = error,
                color = MaterialTheme.colorScheme.error
            )
        }
    }
}
```

## Managing the RIB Tree

The root of your app manages the RIB tree:

```kotlin
class RootRouter(
    override val interactor: RootInteractor
) : Router<RootInteractor>, LoginInteractor.Listener {
    
    private var loginRouter: LoginRouter? = null
    private var homeRouter: HomeRouter? = null
    
    fun attachLogin() {
        val builder = LoginBuilder(object : LoginBuilder.LoginDependency {
            override val loginListener = this@RootRouter
        })
        loginRouter = builder.build()
        attachChild(loginRouter!!)
    }
    
    override fun onLoginSuccess(userId: String) {
        loginRouter?.let { detachChild(it) }
        loginRouter = null
        attachHome(userId)
    }
    
    private fun attachHome(userId: String) {
        // Build and attach HomeRouter
    }
}
```

## Integrating with Compose Navigation

For a more seamless Compose integration:

```kotlin
@Composable
fun RootApp(rootRouter: RootRouter) {
    val currentRib by rootRouter.currentRib.collectAsState()
    
    MaterialTheme {
        AnimatedContent(
            targetState = currentRib,
            transitionSpec = {
                fadeIn() + slideInHorizontally() togetherWith
                fadeOut() + slideOutHorizontally()
            }
        ) { rib ->
            when (rib) {
                is LoginRouter -> LoginScreen(rib.interactor)
                is HomeRouter -> HomeScreen(rib.interactor)
            }
        }
    }
}
```

## Key Takeaways

1. **Separation of Concerns**: RIBs enforces clear boundaries between navigation, business logic, and UI
2. **Compose Compatibility**: Jetpack Compose works naturally as the view layer
3. **Scalability**: The architecture scales well for large, complex applications
4. **Testability**: Each component can be tested independently

## Conclusion

RIBs with Jetpack Compose gives you the best of both worlds—a battle-tested architecture for managing complexity, combined with the modern declarative UI paradigm. While it may feel like overkill for smaller apps, it shines when building large-scale applications with complex navigation and business logic requirements.

The key is understanding when to use it. For simple apps, MVVM with Compose might be sufficient. But when your app grows to have deeply nested flows, complex state management, and multiple teams working on different features, RIBs provides the structure you need to maintain sanity.

---

*Have questions or want to dive deeper into any aspect of RIBs? Feel free to reach out!*

## Resources

- [Uber RIBs GitHub Repository](https://github.com/uber/RIBs)
- [RIBs Documentation](https://github.com/uber/RIBs/wiki)
- [Jetpack Compose Documentation](https://developer.android.com/jetpack/compose)

