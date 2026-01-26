---
layout: post
title: "SavedState internal mechanism for quicker access"
date: 2025-02-14 10:00:00 +0300
---

Android keeps a serialized copy of the data in memory, outside of your process. Depending on various factors, the system might try to optimize this process and leave the same Bundle object in memory without serialization for quicker access. These behaviors however, may change across Android API versions.

