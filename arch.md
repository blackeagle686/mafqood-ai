# Athar — Posts & AI Architecture Reference
### For: Senior Performance Engineer — Load Testing & Optimization
### Generated: 2026-07-26 | Source: Codebase Static Analysis

---

> **Audience**: This document is written for a performance engineer who needs to understand the system's
> internal architecture, critical data paths, I/O boundaries, and concurrency characteristics to design
> effective load tests and identify optimization opportunities.

---

## Table of Contents

1. [System Overview & High-Level Architecture](#1-system-overview--high-level-architecture)
2. [Deep Dive: The "Post" Subsystem & Data Flow](#2-deep-dive-the-post-subsystem--data-flow)
3. [AI Integration & Asynchronous Workflow](#3-ai-integration--asynchronous-workflow)
4. [Optimization & Load Testing Focus Areas](#4-optimization--load-testing-focus-areas)

---

## 1. System Overview & High-Level Architecture

### 1.1 Technology Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| **Runtime** | ASP.NET Core | .NET 9.0 | Single-project vertical-slice architecture |
| **ORM** | Entity Framework Core | 9.0.13 | Code-first, SQL Server provider |
| **Database** | SQL Server | Remote hosted | Separate DBs for app data and Hangfire |
| **Auth** | ASP.NET Identity + JWT | — | `JwtBearerDefaults`, 30-min token expiry |
| **CQRS Mediator** | MediatR | 14.0.0 | Command/Query separation, pipeline behaviors |
| **Validation** | FluentValidation | 12.1.1 | Auto-validation via MediatR pipeline |
| **Object Mapping** | Mapster | 7.4.0 | Assembly-scanned configuration |
| **Background Jobs** | Hangfire | 1.8.23 | SQL Server storage, recurring + fire-and-forget |
| **Real-time** | SignalR | Built-in | 4 hubs, WebSocket transport, in-memory groups |
| **Push Notifications** | Firebase Admin SDK | 3.1.0 | FCM for Android/iOS push |
| **Email** | MailKit | 4.16.0 | Brevo SMTP relay |
| **HTTP Resilience** | Polly | 9.0.0 | Retry, Circuit Breaker, Timeout for AI calls |
| **Payments** | Stripe.net | 51.1.0 | FamilyCare subscriptions |
| **Caching** | `IDistributedCache` | In-memory | Used for location presence tracking |
| **API Docs** | Swashbuckle | 9.0.6 | Swagger UI with JWT auth |

### 1.2 Architectural Pattern

The project uses a **Vertical Slice Architecture** with **CQRS** (Command Query Responsibility Segregation):

- **No traditional layered architecture** (no separate Application/Domain/Infrastructure projects).
- Each feature is a **self-contained folder** under `Features/` containing: Endpoint (thin controller) → Request (MediatR `IRequest` + FluentValidation) → Handler (business logic) → Response DTO.
- **MediatR Pipeline Behavior**: `ValidationHandler<TRequest, TResponse>` intercepts all requests and runs FluentValidation before the handler executes.
- **Result Pattern**: All handlers return `Result<T>` (not exceptions) for business errors. `ResultExtensions.ToResponse()` maps to HTTP status codes.

### 1.3 High-Level Integration Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        FLUTTER["Flutter Mobile App<br/>(Android / iOS)"]
    end

    subgraph "ASP.NET Core 9 Backend"
        direction TB
        API["REST API Controllers<br/>(Vertical Slice Endpoints)"]
        MEDIATR["MediatR Pipeline<br/>(Validation → Handler)"]
        SIGNALR["SignalR Hubs<br/>(Chat, Location, Posts, Notifications)"]
        HANGFIRE["Hangfire Job Server<br/>(Background Processing)"]
        NOTIF_PIPE["Notification Pipeline<br/>(Persist → Dispatch)"]
        FILE_SVC["FileService<br/>(wwwroot Disk I/O)"]
        CONN_MGR["ConnectionManager<br/>(In-Memory Singleton)"]
    end

    subgraph "Data Stores"
        SQL_APP[("SQL Server<br/>App Database<br/>(Posts, Users, Chat,<br/>Notifications, FamilyCare)")]
        SQL_HF[("SQL Server<br/>Hangfire Database<br/>(Job Queue and State)")]
        DISK[("wwwroot/<br/>Static File Storage<br/>(Images, Documents)")]
    end

    subgraph "External Services & Subsystems"
        FCM_SVC["Firebase Cloud Messaging<br/>(Push Notifications)"]
        SMTP_SVC["Brevo SMTP Relay<br/>(Transactional Email)"]
        STRIPE_SVC["Stripe API<br/>(Payment Processing)"]
        GOOGLE_SVC["Google OAuth 2.0<br/>(Social Sign-In)"]
        
        subgraph "Mafqood AI (Python)"
            AI_API["Django DRF API"]
            AI_WORKER["Celery Workers<br/>(InsightFace / Matching)"]
            AI_VDB[("ChromaDB<br/>(Vector Store)")]
        end
    end

    FLUTTER -->|"HTTPS REST"| API
    FLUTTER <-->|"WebSocket"| SIGNALR

    API --> MEDIATR
    MEDIATR --> SQL_APP
    MEDIATR --> FILE_SVC
    FILE_SVC --> DISK
    MEDIATR -->|"Enqueue Job"| HANGFIRE

    HANGFIRE -->|"HTTP POST/PUT/DELETE"| AI_API
    HANGFIRE --> SQL_HF
    HANGFIRE --> SQL_APP

    AI_API -->|"Enqueue Task"| AI_WORKER
    AI_WORKER <-->|"Embeddings"| AI_VDB
    AI_WORKER -->|"HTTP POST Callback<br/>/api/ai/match-results"| API

    MEDIATR -->|"Publish Event"| NOTIF_PIPE
    NOTIF_PIPE -->|"Persist"| SQL_APP
    NOTIF_PIPE -->|"SignalR Push"| SIGNALR
    NOTIF_PIPE -->|"FCM Push"| FCM_SVC

    SIGNALR --> CONN_MGR
    MEDIATR --> SMTP_SVC
    MEDIATR --> STRIPE_SVC
    API --> GOOGLE_SVC

    style AI_API fill:#ff9800,stroke:#e65100,color:#000
    style AI_WORKER fill:#ff9800,stroke:#e65100,color:#000
    style AI_VDB fill:#533483,stroke:#e94560,color:#fff
    style SQL_APP fill:#1565c0,stroke:#0d47a1,color:#fff
    style HANGFIRE fill:#7b1fa2,stroke:#4a148c,color:#fff
    style NOTIF_PIPE fill:#2e7d32,stroke:#1b5e20,color:#fff
    style SIGNALR fill:#00838f,stroke:#006064,color:#fff
```

### 1.4 Request Lifecycle Summary

Every API request traverses this pipeline:

```
HTTP Request
  → ASP.NET Controller (Endpoint)
    → mediator.Send(request)
      → ValidationHandler<T> (FluentValidation — rejects invalid requests)
        → Feature Handler (business logic, DB ops, events)
          → Result<T> returned
    → result.ToResponse() → HTTP Response
```

> [!IMPORTANT]
> The MediatR pipeline is synchronous within the request scope. All `INotification` (domain events) published via `mediator.Publish()` execute **in-process and block the HTTP response** unless explicitly wrapped in `Task.Run` or Hangfire.

---

## 2. Deep Dive: The "Post" Subsystem & Data Flow

### 2.1 Post Entity Data Structure

The `Post` entity (defined in `Entities/Posts/Post.cs`) represents a Lost or Found person/item report:

```csharp
public class Post
{
    public int Id { get; set; }                    // Auto-increment PK

    // ── Owner ────────────────────────────────────
    public string UserId { get; set; }             // FK → AspNetUsers.Id
    public ApplicationUser User { get; set; }

    // ── Content ──────────────────────────────────
    public string? ImageUrl { get; set; }           // Relative path: "Images/{guid}.jpg"
    public string? Description { get; set; }        // Free-text description

    // ── Geospatial ───────────────────────────────
    public double Latitude { get; set; }            // WGS84 decimal degrees
    public double Longitude { get; set; }           // WGS84 decimal degrees

    // ── Classification ───────────────────────────
    public PostType Type { get; set; }              // Lost = 0, Found = 1
    public PostStatus Status { get; set; }          // Active = 0, Resolved = 1

    // ── Engagement Counters ──────────────────────
    public int LikesCount { get; set; }             // Denormalized counter
    public int DislikesCount { get; set; }          // Denormalized counter

    // ── Timestamps ───────────────────────────────
    public DateTime CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }

    // ── Navigation Properties ────────────────────
    public List<PostComment> Comments { get; set; } // Threaded (self-join via ParentCommentId)
    public List<SavedPost> SavedByUsers { get; set; }
    public List<PostReact> Reacts { get; set; }     // Like/Dislike per user
}
```

**Related entities involved in a Post's lifecycle**:

| Entity | Relationship | Key Fields |
|---|---|---|
| `PostComment` | One-to-Many | `PostId`, `UserId`, `Text`, `ParentCommentId` (threaded replies) |
| `PostReact` | Many-to-Many (composite PK) | `UserId`, `PostId`, `ReactType` (Like/Dislike) |
| `SavedPost` | Many-to-Many (composite PK) | `UserId`, `PostId`, `SavedAt` |
| `AiMatchResult` | Many-to-Many (via AI) | `LostPostId`, `FoundPostId`, `ConfidenceScore`, `MatchedAt` |

### 2.2 Post CRUD Operations

| Operation | Endpoint | Handler | AI Sync | Notification |
|---|---|---|---|---|
| **Create** | `POST /posts` | `CreatePostHandler` | Hangfire enqueue | `PostCreatedEvent` → followers |
| **Update** | `PUT /posts/{id}` | `UpdatePostHandler` | Hangfire enqueue | None |
| **Delete** | `DELETE /posts/{id}` | `DeletePostHandler` | Hangfire enqueue | None |
| **Get by ID** | `GET /posts/{id}` | `GetPostByIdHandler` | None | None |
| **Get all** | `GET /posts` | `GetPostsHandler` | None | None |

### 2.3 Create Post — Full Data Flow Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as Flutter Client
    participant EP as CreatePostEndpoint<br/>(API Controller)
    participant MP as MediatR Pipeline
    participant VH as ValidationHandler<br/>(FluentValidation)
    participant CH as CreatePostHandler
    participant FS as FileService<br/>(Disk I/O)
    participant DB as SQL Server<br/>(EF Core)
    participant MR as MediatR<br/>(Event Bus)
    participant NEH as PostCreated<br/>EventHandler
    participant NS as NotificationService
    participant ND as NotificationDispatcher
    participant SR as SignalR Hub
    participant FCM as Firebase FCM
    participant HF as Hangfire<br/>(Job Queue)
    participant AI_API as Mafqood AI API
    participant AI_W as Mafqood Celery Worker

    User->>+EP: POST /posts<br/>[FromForm] Image, Type, Lat, Lng, Description
    EP->>+MP: mediator.Send(CreatePostRequest)

    MP->>+VH: Pipeline Behavior: Validate
    Note over VH: FluentValidation checks:<br/>Type in {Lost, Found}<br/>Image not null<br/>Lat/Lng not null<br/>Description not empty
    alt Validation Fails
        VH-->>EP: Result.Failure (400)
        EP-->>User: HTTP 400 + error details
    end
    VH->>-MP: Validation passed

    MP->>+CH: Handle(CreatePostRequest)

    rect rgba(255, 152, 0, 0.15)
        Note over CH,FS: PHASE 1: Image Persistence (Disk I/O)
        CH->>+FS: SaveFileAsync(image, Images/, extensions, maxBytes)
        Note over FS: Validates extension and size<br/>Generates GUID filename<br/>Async FileStream write (81920 buffer)<br/>Returns relative path
        FS-->>-CH: Result of Images/{guid}.jpg
    end

    rect rgba(33, 150, 243, 0.15)
        Note over CH,DB: PHASE 2: Database Persistence
        CH->>+DB: postRepository.AddAsync(Post entity)
        CH->>DB: postRepository.SaveChangesAsync()
        Note over DB: INSERT INTO Posts<br/>(UserId, ImageUrl, Lat, Lng,<br/>Description, Type, Status, CreatedAt)
        DB-->>-CH: Post.Id assigned (auto-increment)
    end

    rect rgba(76, 175, 80, 0.15)
        Note over CH,FCM: PHASE 3: Follower Notification (IN-PROCESS, BLOCKING)
        CH->>+MR: mediator.Publish(PostCreatedEvent)
        MR->>+NEH: Handle PostCreatedEvent
        Note over NEH: Query: SELECT UserId FROM Followers<br/>WHERE FollowedUserId = authorId
        loop For each follower
            NEH->>+NS: CreateNotificationAsync(model)
            Note over NS: 1. Check ProcessedEvents (idempotency)<br/>2. INSERT Notification + ProcessedEvent<br/>3. SaveChanges (atomic)
            NS->>+ND: DispatchAsync(notification)
            ND->>SR: SignalR: ReceiveNotification + BadgeCountUpdated
            ND->>FCM: FCM: Push to all user devices
            ND-->>-NS: Dispatch complete
            NS-->>-NEH: Notification persisted
        end
        NEH-->>-MR: All followers notified
        MR-->>-CH: Event handling complete
    end

    rect rgba(156, 39, 176, 0.15)
        Note over CH,AI: PHASE 4: AI Sync (ASYNC, NON-BLOCKING)
        CH->>CH: Check aiOptions.Enabled
        alt AI Enabled
            CH->>CH: Task.Run captures postId, userId, postType, imageUrl by value
            CH-->>HF: BackgroundJob.Enqueue of AiPostSyncJob
            Note over HF: Job serialized to<br/>Hangfire SQL Server DB
        end
    end

    CH-->>-MP: Result.Success(CreatePostResponse)
    MP-->>-EP: Result of CreatePostResponse
    EP-->>-User: HTTP 200 + {id, imageUrl, lat, lng, ...}

    Note over HF,AI: Asynchronous (after HTTP response returned)

    rect rgba(244, 67, 54, 0.15)
        HF->>+AI_API: HTTP POST /api/ai/posts<br/>{userId, postId, postType, imageUrl}
        Note over HF,AI_API: Headers: X-Api-Key, Accept: application/json<br/>Polly: Retry 3x (2s, 4s, 8s) + Circuit Breaker<br/>(5 failures then 30s open) + 10s Timeout
        AI_API-->>-HF: 202 Accepted (queued)
    end

    Note over AI_API,AI_W: Background processing (InsightFace, ChromaDB)
    AI_API->>AI_W: Enqueue Task
    Note over AI_W: Extract 512-d Face Embeddings<br/>Cross-match Lost & Found (Vector DB)
    AI_W->>EP: Webhook: POST /api/ai/match-results<br/>{userId, postId, matchedResults[]}
    Note over EP: Validated via X-Api-Key header
```

### 2.4 Feed Ranking Algorithm

When users query the feed, posts are scored using a **weighted multi-factor algorithm** (defined in `PostScoringService`):

```
Score = (LocationScore x 70) + (TimeScore x 20) + (FollowerScore x 10)
```

| Component | Weight | Formula | Decay Model |
|---|---|---|---|
| **Location** | 70 | `HalfLifeKm / (HalfLifeKm + distanceKm)` | Inverse-hyperbolic decay. Floor = 0.03 |
| **Time** | 20 | `e^(-ln(2) / halfLifeHours x ageHours)` | Exponential decay. Half-life = 48h |
| **Follower** | 10 | `1.0` if following, `0.0` otherwise | Binary |

> [!WARNING]
> **Performance-critical**: `MaxFeedBatchSize = 2000` posts are loaded into memory for in-memory scoring. The Haversine distance calculation (trigonometric) runs per-post per-request. With 2000 posts and 100 concurrent feed requests, this is 200,000 Haversine computations per second.

---

## 3. AI Integration & Asynchronous Workflow

### 3.1 Communication Protocol

The C# backend communicates with the Python AI microservice over **synchronous HTTP REST**, wrapped in **Polly resilience policies** and decoupled from the user request via **Hangfire background jobs**.

| Aspect | Detail |
|---|---|
| **Transport** | HTTP/HTTPS (REST) |
| **AI Base URL** | Configurable via `appsettings.json` → `AiModel:BaseUrl` |
| **Tunneling** | ngrok (development/staging) |
| **Authentication** | Shared API key via `X-Api-Key` header (symmetric, both directions) |
| **Serialization** | JSON (`camelCase` naming policy) |
| **Content-Type** | Explicit `StringContent` (not `JsonContent`) — required for Polly retry compatibility |

### 3.2 AI Service Interface

The C# → Python contract is defined in `IAiModelService`:

```csharp
public interface IAiModelService
{
    Task SendPostAsync(string userId, int postId, PostType postType, string imageUrl);
    Task UpdatePostAsync(string userId, int postId, PostType postType, string imageUrl);
    Task DeletePostAsync(int postId, string userId, PostType postType, string imageUrl);
    Task MarkPostResolvedAsync(string userId, int postId);
}
```

> [!IMPORTANT]
> **Critical implementation detail** (from `AiModelService.cs`): The `imageUrl` sent to the AI service is converted from a relative path (`Images/abc.jpg`) to an **absolute public URL** (`https://athar.runasp.net/Images/abc.jpg`). The AI service **downloads the image** from this URL — meaning the C# backend's static file server must handle the AI service's download requests concurrently with user traffic.

### 3.3 Polly Resilience Pipeline

Three policies are chained on the `HttpClient` pipeline (configured in `DependencyInjection.cs`):

```mermaid
graph LR
    subgraph "Polly Policy Chain (per HTTP request to AI)"
        A["Retry Policy<br/>3 retries<br/>Exponential: 2s, 4s, 8s"]
        B["Circuit Breaker<br/>5 consecutive failures<br/>then 30s open circuit"]
        C["Timeout Policy<br/>10s per-request timeout"]
    end

    REQ["Hangfire Worker<br/>HTTP Request"] --> A --> B --> C --> SVC["Python AI Service"]

    style A fill:#fff3e0,stroke:#e65100,color:#000
    style B fill:#fce4ec,stroke:#c62828,color:#000
    style C fill:#e8eaf6,stroke:#283593,color:#000
```

**Worst-case latency per AI sync**: 3 retries x (2+4+8)s backoff + 10s timeout = **up to 24 seconds** before giving up. This is why the call MUST NOT be on the HTTP request path.

### 3.4 Asynchronous Processing Pattern — Complete Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as Flutter Client
    participant API as C# API Handler
    participant DB as SQL Server<br/>(App DB)
    participant DISK as wwwroot/<br/>(Static Files)
    participant HF_DB as SQL Server<br/>(Hangfire DB)
    participant HF as Hangfire Worker
    participant AI_API as Mafqood AI API
    participant AI_W as Mafqood Celery Worker
    participant CALLBACK as ReceiveMatchResults<br/>Endpoint
    participant MATCH_H as ReceiveMatchResults<br/>Handler
    participant NOTIF as Notification Pipeline
    participant CLIENT as Flutter Client<br/>(via SignalR + FCM)

    rect rgba(76, 175, 80, 0.15)
        Note over User,DISK: USER REQUEST SCOPE (target: 200-500ms)
        User->>+API: POST /posts {image, metadata}
        API->>DISK: Save image to wwwroot/Images/
        API->>DB: INSERT Post (returns Post.Id)
        API->>API: Task.Run then Hangfire.Enqueue()
        API-->>-User: 200 OK {postId, imageUrl, ...}
        Note over User: User sees immediate response.<br/>AI processing is invisible.
    end

    rect rgba(156, 39, 176, 0.15)
        Note over HF_DB,AI: HANGFIRE WORKER SCOPE (seconds to minutes later)
        Note over HF: Hangfire polls HF_DB for<br/>pending jobs (approx 15s interval)
        HF_DB-->>HF: Dequeue AiPostSyncJob
        HF->>+AI_API: POST /api/ai/posts<br/>{userId, postId, postType,<br/>imageUrl: https://athar.runasp.net/Images/x.jpg}
        Note over AI_API: AI downloads image from<br/>athar.runasp.net/Images/x.jpg<br/>via public static file server

        alt Success
            AI_API-->>HF: 202 Accepted
            HF->>HF_DB: Mark job succeeded
            AI_API->>AI_W: Enqueue Celery Task
        else Transient Failure
            AI_API-->>HF: 500 or Timeout
            Note over HF: Polly retries (2s, 4s, 8s)<br/>If all 3 fail then Hangfire auto-retries<br/>with its own schedule (10 attempts)
        end
        deactivate AI_API
    end

    rect rgba(255, 152, 0, 0.15)
        Note over AI_W,CLIENT: AI CALLBACK SCOPE (minutes to hours later)
        Note over AI_W: AI Worker completes image analysis:<br/>1. InsightFace detection (512-d embedding)<br/>2. ChromaDB similarity search<br/>3. Cross-matching Lost with Found
        AI_W->>+CALLBACK: POST /api/ai/match-results<br/>X-Api-Key: shared-secret<br/>{userId, postId, matchedResults[<br/>  {userId, postId, confidenceScore}]}
        CALLBACK->>CALLBACK: Validate X-Api-Key header
        CALLBACK->>+MATCH_H: mediator.Send(ReceiveMatchResultsRequest)
    end

    rect rgba(33, 150, 243, 0.15)
        Note over MATCH_H,CLIENT: MATCH PROCESSING AND NOTIFICATION
        MATCH_H->>DB: Validate source post exists and not resolved
        MATCH_H->>DB: Filter self-matches
        loop For each match result
            MATCH_H->>DB: UPSERT AiMatchResult<br/>(LostPostId, FoundPostId, ConfidenceScore)
        end
        MATCH_H->>DB: SaveChangesAsync()

        MATCH_H->>MATCH_H: Generate deterministic EventIds<br/>(SHA-256 hash of match params)

        par Notify query-post owner
            MATCH_H->>+NOTIF: Publish AiMatchResultEvent<br/>(for post owner who triggered the match)
            NOTIF->>DB: Idempotency check (ProcessedEvents)
            NOTIF->>DB: INSERT Notification
            NOTIF->>CLIENT: SignalR: ReceiveNotification
            NOTIF->>CLIENT: FCM: Push notification
            deactivate NOTIF
        and Notify matched-post owners
            loop For each matched post (different owner)
                MATCH_H->>+NOTIF: Publish AiMatchResultEvent<br/>(for matched post owner)
                NOTIF->>DB: INSERT Notification
                NOTIF->>CLIENT: SignalR + FCM
                deactivate NOTIF
            end
        end

        MATCH_H-->>-CALLBACK: Result.Success()
        CALLBACK-->>-AI: 200 OK
    end
```

### 3.5 Idempotency Strategy (Critical for Load Testing)

The system implements **two-level idempotency** to handle duplicate AI callbacks and concurrent notifications:

| Level | Mechanism | Location |
|---|---|---|
| **Application** | `ProcessedEvents` table check before creating notification | `NotificationService.CreateNotificationAsync()` |
| **Database** | `UNIQUE` constraint on `Notification.EventId` | Catches race conditions when app-level check passes concurrently |
| **Deterministic EventId** | `SHA-256("ai-match:{userId}:{lostPostId}:{foundPostId}:{role}")` → first 16 bytes as Guid | `ReceiveMatchResultsHandler.GenerateDeterministicEventId()` |

> [!NOTE]
> The deterministic EventId generation means that if the AI service sends the same match results twice (network retry, duplicate webhook), the system produces identical EventIds and the idempotency guard prevents duplicate notifications. This must be validated under load.

### 3.6 AI Sync Lifecycle Across All Post Operations

```mermaid
flowchart TD
    subgraph "Post Lifecycle Events"
        CREATE["CreatePostHandler<br/>POST /posts"]
        UPDATE["UpdatePostHandler<br/>PUT /posts/{id}"]
        DELETE["DeletePostHandler<br/>DELETE /posts/{id}"]
    end

    subgraph "Async Decoupling Layer"
        TASKRUN["Task.Run then<br/>BackgroundJob.Enqueue()"]
        HFDB[("Hangfire<br/>SQL Server DB")]
        HFWORKER["Hangfire Worker<br/>Thread Pool"]
    end

    subgraph "AiPostSyncJob Methods"
        SYNC_NEW["SyncNewPostAsync()"]
        SYNC_UPD["SyncUpdatedPostAsync()"]
        SYNC_DEL["SyncDeletedPostAsync()"]
    end

    subgraph "AiModelService HTTP Calls"
        HTTP_POST["POST /api/ai/posts"]
        HTTP_PUT["PUT /api/ai/posts"]
        HTTP_DEL["DELETE /api/ai/posts"]
    end

    subgraph "Polly Resilience"
        RETRY["Retry 3x<br/>(2s, 4s, 8s)"]
        CB["Circuit Breaker<br/>(5 fails then 30s open)"]
        TIMEOUT["Timeout<br/>(10s per request)"]
    end

    AI_API["Mafqood AI API (Django)"]

    CREATE -->|"Fire and Forget"| TASKRUN
    UPDATE -->|"Fire and Forget"| TASKRUN
    DELETE -->|"Fire and Forget"| TASKRUN

    TASKRUN --> HFDB
    HFDB --> HFWORKER

    HFWORKER --> SYNC_NEW
    HFWORKER --> SYNC_UPD
    HFWORKER --> SYNC_DEL

    SYNC_NEW --> HTTP_POST
    SYNC_UPD --> HTTP_PUT
    SYNC_DEL --> HTTP_DEL

    HTTP_POST --> RETRY
    HTTP_PUT --> RETRY
    HTTP_DEL --> RETRY

    RETRY --> CB --> TIMEOUT --> AI_API

    style CREATE fill:#c8e6c9,stroke:#2e7d32,color:#000
    style UPDATE fill:#fff9c4,stroke:#f9a825,color:#000
    style DELETE fill:#ffcdd2,stroke:#c62828,color:#000
    style HFDB fill:#e1bee7,stroke:#7b1fa2,color:#000
    style AI_API fill:#ff9800,stroke:#e65100,color:#000
```

---

## 4. Optimization & Load Testing Focus Areas

### 4.1 Write-Heavy Operations — Concurrency Hotspots

#### 4.1.1 Post Creation Concurrency

| Concern | Detail | Risk Level |
|---|---|---|
| **Disk I/O contention** | `FileService.SaveFileAsync()` writes to `wwwroot/Images/` using `FileStream` with 81920-byte buffer and `FileShare.None`. Under concurrent writes, OS-level file creation is serialized per-directory. | Medium |
| **DB write amplification** | A single `CreatePost` triggers: 1 INSERT (Post) + N INSERTs (Notifications for N followers) + N INSERTs (ProcessedEvents) + potentially N SignalR + N FCM calls — **all within the same HTTP request**. | High |
| **Follower fan-out** | Users with many followers create O(N) notifications synchronously. A user with 1000 followers = 1000 DB inserts + 1000 SignalR pushes + 1000 FCM calls before the HTTP response returns. | **Critical** |
| **Hangfire enqueue race** | `Task.Run(() => BackgroundJob.Enqueue(...))` is fire-and-forget. Under heavy load, Hangfire SQL inserts may contend with app DB traffic on the same SQL Server. | Medium |

> [!CAUTION]
> **Load Test Scenario**: Simulate 100 concurrent users creating posts, where 10% of those users have 500+ followers. Measure p99 response time and DB connection pool exhaustion.

#### 4.1.2 AI Match Callback Concurrency

| Concern | Detail | Risk Level |
|---|---|---|
| **UPSERT pattern** | `ReceiveMatchResultsHandler` does a `FindAsync` + conditional `AddAsync`/`UpdateAsync` per match — no DB-level upsert. Under concurrent callbacks for the same Lost-Found pair, this can cause duplicate key violations (caught by UNIQUE constraint). | Medium |
| **Notification fan-out** | Each match generates 2 notifications (query owner + matched owner), each with SignalR + FCM dispatch. A callback with 10 matches = 20 notifications in a single request. | Medium |
| **Deterministic EventId collision** | By design, duplicate callbacks produce identical EventIds — handled by ProcessedEvents table. Load test should verify this idempotency holds under concurrent duplicate callbacks. | Low (by design) |

> [!TIP]
> **Load Test Scenario**: Send 50 concurrent AI callback requests with overlapping match pairs to validate idempotency produces exactly 0 duplicate notifications.

### 4.2 I/O and Network Bottlenecks

#### 4.2.1 Image Pipeline Bottleneck

```mermaid
flowchart LR
    subgraph "Upload Path (User to Server)"
        A["Flutter Client"] -->|"multipart/form-data<br/>Image payload"| B["Kestrel Web Server"]
        B -->|"IFormFile in memory"| C["FileService"]
        C -->|"FileStream write<br/>81920-byte buffer"| D[("wwwroot/Images/<br/>Local Disk")]
    end

    subgraph "Download Path (AI from Server)"
        E["Python AI Service"] -->|"HTTP GET<br/>Full image download"| F["Kestrel Static Files<br/>UseStaticFiles()"]
        F -->|"Read from disk"| D
    end

    style D fill:#ffcc80,stroke:#e65100,color:#000
    style A fill:#81c784,stroke:#2e7d32,color:#000
    style E fill:#ff9800,stroke:#e65100,color:#000
```

**Key bottleneck**: When a post is created, the image is uploaded to disk. Shortly after, the AI service downloads that same image from the server's static file middleware. Under load:

- **Disk I/O**: Concurrent uploads and AI downloads compete for the same disk.
- **Network bandwidth**: Large images (up to `MaxImageBytes`) are transferred twice — once uploaded by the user, once downloaded by the AI service.
- **Static file middleware**: `UseStaticFiles()` is not rate-limited. The AI service could saturate the download bandwidth.

> [!WARNING]
> **Load Test Scenario**: Upload 200 images in 60 seconds while the AI service simultaneously downloads 200 previously-uploaded images. Monitor disk queue length and network saturation.

#### 4.2.2 AI Service Latency & Timeout

| Parameter | Value | Impact |
|---|---|---|
| Per-request timeout | **10 seconds** | If the AI service is slow, Polly kills the request at 10s |
| Retry backoff | **2s → 4s → 8s** (14s total) | Worst case = 10s + 14s = 24s per sync attempt |
| Circuit breaker threshold | **5 consecutive failures** | After 5 failures, circuit opens for 30s — all AI syncs fail-fast |
| Hangfire auto-retry | **10 attempts** (default) | Failed jobs retry with increasing delays over hours |

> [!TIP]
> **Load Test Scenario**: Simulate AI service degradation (artificial 8s latency) and observe: Do Hangfire queues back up? Does the circuit breaker open correctly? What happens to post creation throughput?

#### 4.2.3 SignalR Connection Scaling

| Component | Implementation | Bottleneck |
|---|---|---|
| `ConnectionManager` | `ConcurrentDictionary<string, HashSet<string>>` (Singleton, in-memory) | Single-server only. Under 10K+ concurrent connections, `lock(connections)` per user becomes a contention point |
| SignalR groups | In-memory (no Redis backplane) | Cannot scale horizontally without adding `AddStackExchangeRedis()` |
| Notification delivery | Sequential `foreach` over all delivery channels | If FCM is slow, SignalR delivery waits (channels execute sequentially within the dispatcher) |

> [!TIP]
> **Load Test Scenario**: Establish 5000 concurrent WebSocket connections across all 4 hubs and measure message delivery latency under sustained notification load.

### 4.3 Potential Optimization Ideas (For Discussion)

*Note: The ideas listed below are initial thoughts based on the current architecture. I am looking forward to your architectural review and guidance on the best approach for these bottlenecks during our load testing phase.*

#### 4.3.1 Critical — Follower Notification Fan-out

**Problem**: Creating a post triggers synchronous in-process notification for every follower, blocking the HTTP response.

**Potential Approach**:
```diff
- Current Flow:
-   HTTP Handler → mediator.Publish(PostCreatedEvent)
-     → loop N followers → N DB writes → N SignalR → N FCM
-     → HTTP 200 (delayed by all N iterations)

+ Proposed Flow:
+   HTTP Handler → Hangfire.Enqueue(NotifyFollowersJob)
+     → HTTP 200 (immediate, sub-100ms)
+   Hangfire Worker → batch followers
+     → batch INSERT notifications → batch SignalR → batch FCM

```

#### 4.3.2 High — Feed Scoring In-Memory Computation

**Problem**: `MaxFeedBatchSize = 2000` posts loaded into memory, each requiring a Haversine calculation.

**Idea to Explore**:

* Implement spatial indexing (SQL Server `geography` type or in-memory R-tree) for pre-filtering by bounding box.
* Cache scored feeds per user-location grid cell with short TTL (30-60 seconds).
* Consider pre-computed materialized views for "top posts near location" with periodic refresh.

#### 4.3.3 High — Connection Pool Tuning

**Problem**: Two separate SQL Server databases (app + Hangfire) share the default connection pool settings.

**Idea to Explore**:

* Explicitly configure `Max Pool Size` in connection strings (default is 100).
* Under load with concurrent post creation + AI callbacks + Hangfire polling, the pool can exhaust.
* Monitor with `sys.dm_exec_connections` and EF Core diagnostic events.

#### 4.3.4 Medium — Notification Dispatcher Parallelism

**Problem**: `NotificationDispatcher` iterates delivery channels sequentially (`foreach`). If FCM takes 2s, SignalR delivery for the same notification is delayed.

**Idea to Explore**:

```diff
- // Current: Sequential
- foreach (var channel in channels)
-     await channel.DeliverAsync(notification, ct);

+ // Proposed: Parallel
+ await Task.WhenAll(channels.Select(ch => ch.DeliverAsync(notification, ct)));

```

#### 4.3.5 Medium — CQRS Read-Side Caching

**Problem**: Post queries (feed, search, get-by-id) hit the database on every request with no caching layer.

**Idea to Explore**:

* Cache `GetPostById` responses with `IDistributedCache` (2-5 minute TTL).
* Cache feed results per user-location cell (invalidate on new post in same cell).
* Implement ETag/If-None-Match for client-side caching of unchanged feeds.

#### 4.3.6 Low — Static File CDN Offload

**Problem**: Image serving and AI download both hit the same Kestrel process and local disk.

**Idea to Explore**:

* Offload `wwwroot/Images/` to Azure Blob Storage or AWS S3 with CDN.
* Update `AiModelService.ToAbsoluteImageUrl()` to return CDN URLs.
* Eliminates disk I/O contention between user uploads and AI image downloads.

---

## 5. Mafqood AI Subsystem Architecture (Python)

### 5.1 AI Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Web Framework** | Django 6 + DRF | API endpoints, serialization, dual JSON/HTML rendering |
| **Face Recognition**| InsightFace (`buffalo_l`) + ONNX | Face detection, alignment, and 512-d embeddings |
| **Computer Vision** | OpenCV 4.8 + ONNX Runtime | Image/video decoding, frame sampling, neural re-aging |
| **DNA Matching** | Forensic Loci Algorithm | Direct, Parent-Child, and Sibling STR matching |
| **Vector DB** | ChromaDB 0.4 | Fast Approximate Nearest-Neighbor (ANN) lookups |
| **Task Queue** | Celery 5.2 + Redis 7 | Background async tasks (clustering, DNA matching, polling) |
| **Containerization**| Docker + Docker Compose | Full stack orchestration |

### 5.2 Internal AI Architecture Pattern

The AI microservice follows a **Domain-Driven, Layered Architecture**:
- **Presentation Layer**: Exposes the REST API via Django REST Framework (DRF).
- **Pipeline Layer**: Orchestrates complex flows (e.g., `SearchPipeline` for routing image vs. video, `ReportPipeline` for indexing).
- **Service Layer**: Houses the core domain logic (`FaceCVPipeline`, `FaceSearchService`, `AgeProgressionGAN`, `DNASearchService`).
- **Infrastructure Layer**: Manages persistent stores (ChromaDB) and async tasks (Celery/Redis workers).

### 5.3 Face Search & Match Pipeline

#### Request Lifetime & Subsystem Schema

This flowchart illustrates the end-to-end journey of a request originating from the C# backend, flowing through the Python AI services, and returning a high-confidence match notification.

```mermaid
flowchart TD
    %% Styling
    style CSHARP fill:#1565c0,stroke:#0d47a1,color:#fff
    style CSHARP_CB fill:#1565c0,stroke:#0d47a1,color:#fff
    style DRF fill:#ff9800,stroke:#e65100,color:#000
    style CELERY fill:#7b1fa2,stroke:#4a148c,color:#fff
    style CV fill:#c8e6c9,stroke:#2e7d32,color:#000
    style SEARCH fill:#fff3e0,stroke:#e65100,color:#000
    style VDB fill:#533483,stroke:#e94560,color:#fff
    style WHK fill:#fce4ec,stroke:#c62828,color:#000
    
    subgraph "C# Athar Backend"
        CSHARP["Hangfire Worker<br/>(AI Sync Job)"]
        CSHARP_CB["Match Callback Endpoint<br/>(/api/ai/match-results)"]
    end

    subgraph "Mafqood AI Subsystem (Python/Django)"
        DRF["Django DRF API<br/>POST /api/ai/posts"]
        
        subgraph "Async Processing Pipeline (Celery / Redis)"
            CELERY["Celery Task Worker<br/>(process_image_task)"]
            
            subgraph "Service Layer"
                CV["InsightFace (buffalo_l)<br/>Face Detection & 512-d Embedding"]
                SEARCH["FaceSearchService<br/>Cross-Matching & Weighting"]
            end
            
            VDB[("ChromaDB<br/>Vector Database")]
            WHK["WebhookNotifier<br/>(Confidence ≥ 95%)"]
        end
    end

    %% Flow Paths
    CSHARP -- "1. Upload Image + Metadata" --> DRF
    DRF -- "2. 202 Accepted (queued)" --> CSHARP
    
    DRF -- "3. Enqueue Task" --> CELERY
    CELERY -- "4. Process via" --> CV
    CV -- "5. Store & Search" --> VDB
    VDB -- "6. Return Neighbors" --> SEARCH
    SEARCH -- "7. High Confidence Match" --> WHK
    WHK -- "8. HTTP POST JSON Payload" --> CSHARP_CB
```

#### Detailed Execution Sequence

When the C# backend sends a `POST /api/ai/posts` request, the exact synchronous and asynchronous interactions are as follows:

```mermaid
sequenceDiagram
    autonumber
    participant CSharp as C# Hangfire Worker
    participant API as Django DRF API
    participant RP as ReportPipeline
    participant CV as FaceCVPipeline<br/>(InsightFace)
    participant VDB as ChromaDB
    participant FSS as FaceSearchService
    participant WHK as WebhookNotifier
    participant CSharpCB as C# Match Callback API

    CSharp->>+API: POST /api/ai/posts<br/>{userId, postId, postType, imageUrl}
    API->>RP: execute(imageUrl, metadata)
    API-->>-CSharp: 202 Accepted (Background Processing Started)
    
    rect rgba(76, 175, 80, 0.15)
        Note over RP,VDB: PHASE 1: Face Detection & Indexing (Celery Worker)
        RP->>CV: process_image(imageUrl)
        Note over CV: InsightFace detects faces<br/>Extracts 512-d embeddings<br/>Filters faces < 40px
        CV-->>RP: [Face(bbox, embedding)]
        RP->>VDB: upsert(embeddings, metadata)
    end

    rect rgba(255, 152, 0, 0.15)
        Note over RP,WHK: PHASE 2: Cross-Matching & Search
        RP->>FSS: trigger_cross_match(postId)
        FSS->>VDB: search(embedding, top_k, opposite_postType)
        Note over VDB: ANN search using cosine similarity
        VDB-->>FSS: {ids, distances}
        FSS->>FSS: Apply Geo + Status Weighting
    end

    rect rgba(33, 150, 243, 0.15)
        Note over FSS,CSharpCB: PHASE 3: Webhook Delivery
        opt Match Confidence ≥ 95%
            FSS->>WHK: queue_webhook_payload()
            WHK->>CSharpCB: POST /api/ai/match-results<br/>{userId, postId, matchedResults}
        end
    end
```

### 5.4 Specialized AI Subsystems

#### 5.4.1 CPU-Optimized Age Progression
For missing persons cases spanning years, the system utilizes a **CPU-optimized FRAN U-Net** neural model compiled to ONNX. It dynamically processes 5-channel residual age mappings to generate aged variants (+5, +10, +15 years) of a face, which are then seamlessly run through the search pipeline without GPU dependency.

#### 5.4.2 Forensic DNA Matching (Asynchronous)
For DNA reports, the system exposes `/api/ai/dna/posts`. 
- **Algorithm**: Compares Short Tandem Repeat (STR) loci (e.g., D3S1358, vWA, FGA).
- **Matching Types**: Direct (identical), Parent-Child (1 allele overlap per locus), and Sibling.
- **Workflow**: A background Celery task cross-references new profiles against the database. High-confidence matches trigger a dedicated DNA webhook payload back to the C# application.

#### 5.4.3 Video Intelligence
If a video is submitted for search, the `VideoProcessor` component samples frames at configurable intervals, runs them through the `FaceCVPipeline`, and deduplicates faces across frames before querying ChromaDB.

### 5.5 Performance Profiling & Time Complexity

To assist with load testing and capacity planning, the following breakdowns outline the expected time complexity of the underlying AI algorithms and a theoretical execution timeline for a standard AI processing job.

#### 5.5.1 AI Pipeline Algorithm Complexity

| Subsystem Component | Algorithm / Technology | Time Complexity | Bottleneck Profile |
|---|---|---|---|
| **Face Detection** | RetinaFace (CNN) | `O(W × H)` (W, H = Image dimensions) | Compute bound (CPU/GPU) |
| **Feature Extraction** | ArcFace (ResNet) | `O(1)` (Fixed 112x112 pixel crop) | Compute bound (CPU/GPU) |
| **Vector Search (ANN)**| HNSW Graph (ChromaDB) | `O(log N)` (N = stored embeddings) | Memory / RAM Bandwidth |
| **DNA STR Matching** | Array Intersection | `O(N × L)` (N = profiles, L = loci) | Memory / L3 Cache |
| **Age Progression** | FRAN U-Net (ONNX) | `O(P)` (P = model parameters) | Compute bound (High latency) |

#### 5.5.2 Execution Timeline (Single Image Post)

The following Gantt chart illustrates the expected end-to-end latency for a standard image post, assuming no queue wait time and processing on a standard CPU-only worker node. 

```mermaid
gantt
    title Single Post AI Pipeline Latency (Approx CPU Times)
    dateFormat  s
    axisFormat  %S.%L
    
    section C# Backend
    Hangfire HTTP POST     :a1, 0, 0.5s
    Receive Match Webhook  :a2, after c5, 0.5s
    
    section AI Django API
    Validate & Enqueue     :b1, after a1, 0.2s
    
    section AI Celery Worker
    Download Image I/O     :c1, after b1, 0.8s
    Face Detection (ONNX)  :c2, after c1, 1.2s
    Feature Embedding      :c3, after c2, 0.5s
    ChromaDB ANN Search    :c4, after c3, 0.1s
    Weighting & Scoring    :c5, after c4, 0.1s
```

> [!WARNING]
> **Latency Multipliers**: If a post contains a **Video**, the `VideoProcessor` extracts frames at 1 FPS. A 10-second video will run the `Face Detection` and `Feature Embedding` steps **10 times**, scaling the worker phase from ~2.7s to over 15s. Ensure Celery workers are scaled horizontally to prevent queue starvation during video batch processing.
