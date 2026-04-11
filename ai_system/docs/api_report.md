# Mafqood AI: Person Cross-Matching API Report

This document outlines the API endpoints and architectural logic for the intelligent person cross-matching system.

## 1. System Overview
The system identifies matches between "missing" and "found" individuals using face embeddings, temporal context, and geospatial data. It operates in real-time on data insertion and periodically through background reconciliation tasks.

---

## 2. API Endpoints

### 🟢 GET `/api/ai/posts/lost/`
**Purpose**: Retrieves a paginated list of all indexed missing persons.

- **Headers**: 
  - `Accept: application/json`
- **Query Params**:
  - `limit` (int): default `100`
  - `offset` (int): default `0`
- **Response** (`200 OK`):
```json
{
  "isSuccess": true,
  "count": 1,
  "data": [
    {
      "id": "person_unique_id",
      "metadata": {
        "postId": 123,
        "status": "missing",
        "location": "Cairo",
        "original_image": "/uploads/img1.jpg"
      }
    }
  ]
}
```

---

### 🟢 GET `/api/ai/posts/found/`
**Purpose**: Retrieves a paginated list of all indexed found persons.
*Same structure as above.*

---

### 🔵 POST `/api/ai/match-post/`
**Purpose**: Primary entry point for indexing and cross-matching.

- **Headers**:
  - `Content-Type: application/json`
- **Request Body (Exact .NET Schema)**:
```json
{
  "postId": 15,
  "userId": "0198e260-1145-79be-a3d9-2e6f1ad0a7dd",
  "imageUrl": "https://mafqood.runasp.net/Images/lolo_017705eb-f533-4fd8-98be-ddb338665452.jpeg",
  "postType": 0 
}
```
*Note on `postType`: `0` -> Lost (Missing), `1` -> Found.*

- **Response** (`200 OK`):
```json
{
  "isSuccess": true,
  "hasData": true,
  "data": {
    "userId": "0198e260-1145-79be-a3d9-2e6f1ad0a7dd",
    "postId": 15,
    "matches": [
      {
        "matchedPostId": 205,
        "confidenceScore": 0.94
      }
    ]
  }
}
```

---

### 🔴 POST `/api/ai/match/cross-check/`
**Purpose**: Triggers manual background reconciliation.

- **Headers**:
  - `Content-Type: application/json`
- **Request Body**:
```json
{
  "batchSize": 50
}
```
- **Response** (`202 Accepted`):
```json
{
  "isSuccess": true,
  "message": "Background cross-match reconciliation task triggered."
}
```

---

## 3. Matching Intelligence (Scoring)
The system calculates a **Combined Score (0.0 - 1.0)**:
- **Face Similarity (70%)**: Euclidean distance between face embeddings.
- **Time Context (20%)**: Linearly decays over 60 days to prioritize recent cases.
- **Location Context (10%)**: Bonus for exact location matches.

> [!IMPORTANT]
> A Webhook Alert is triggered only if the **Combined Score > 0.50**.

---

## 4. Deduplication & Notifications
Each match pair is stored in the `FaceMatch` table. The system automatically suppresses duplicate notifications for the same pair of IDs, even if detected multiple times across different images or background jobs.
