---
layout: post
title: "What Use Cases Should Really Do (Clean Architecture Notes)"
date: 2025-02-14 10:00:00 +0300
description: "Use cases should orchestrate user-facing flows and domain rules, not wrap tiny helpers or not just delegate calls to repositories."
---

Main takeaway: **use cases are not for wrapping one-line helpers**, they are for orchestrating user-facing flows and domain rules.

## Anti-pattern: wrapping `dropLast()` as a “use case”

A class like this adds **extra complexity** without real test or design value.

```kotlin
class DeleteDigitUseCase {
    fun execute(pin: String): String = pin.dropLast(1)
}
```

Calling the standard function directly is clearer:

```kotlin
val nextPin = pin.dropLast(1)
```

## What should a use case cover?

Higher-level operations that combine **user intent** and **business rules**. Example: an offline-first “save todo” flow.

### Moving real orchestration into the use case

This example captures local save + remote sync + scheduling a retry on failure inside one use case.

```kotlin
class SaveTodoUseCase(
    private val local: LocalTodoDataSource,
    private val remote: RemoteTodoDataSource,
    private val syncScheduler: TodoSyncScheduler
) {
    suspend fun execute(todo: Todo) {
        local.upsert(todo)
        val synced = remote.tryUpsert(todo)
        if (!synced) {
            syncScheduler.schedule(todo.id)
        }
    }
}
```

The business rule is: **“Save” is a user-facing action, and *how* it’s saved is a domain decision.** That belongs in a use case.

## When repository vs. use case?

- If a repository is just combining data sources and contains real orchestration, that **logic can move into a use case**.
- If you keep that repository, then **thin use case wrappers** add little value—call the repository directly.

## Domain rule example

Rules like **“a todo cannot be completed without a due date”** are genuine business logic and fit in a use case.

```kotlin
class CompleteTodoUseCase(
    private val todoRepository: TodoRepository
) {
    suspend fun execute(todoId: String) {
        val todo = todoRepository.get(todoId)
        requireNotNull(todo.dueDate) { "Cannot complete without a due date." }
        todoRepository.markDone(todoId)
    }
}
```

**Summary:** Use cases should **orchestrate** user-visible flows and domain rules. Adding extra classes for single-line helpers makes the architecture **more complex, not better**.
