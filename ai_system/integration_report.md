# Mafqood AI Integration Cheat Sheet (.NET ↔ AI)

---

## 1. Connection Configurations

### Base URL (Remote Host)
* **URL:** `https://disparate-catcher-silenced.ngrok-free.dev`

### Authentication Header
Every request from the `.NET` server to the AI server **MUST** contain this header:
* **Header Key:** `X-Api-Key`
* **Header Value:** `mafqood-shared-secret-key-2026`

---

## 2. API Endpoints Reference

### 2.1. Create / Ingest Post (Lost or Found)
Syncs a newly created post to the AI engine to start matching.
* **HTTP Method:** `POST`
* **URL:** `https://disparate-catcher-silenced.ngrok-free.dev/api/ai/posts`

#### Request Body (JSON)
```json
{
  "userId": "user-1234",
  "postId": 9999,
  "postType": 0,
  "imageUrl": "https://yourcdn.com/images/face_image.jpg"
}
```
* *(Note: `postType`: `0` = Lost Item, `1` = Found Item)*

#### Response Body (HTTP 200 OK)
```json
{
  "isSuccess": true,
  "message": "Post successfully received and queued for matching."
}
```

---

### 2.2. Update Post
Updates the biometric image or information for a post.
* **HTTP Method:** `PUT`
* **URL:** `https://disparate-catcher-silenced.ngrok-free.dev/api/ai/posts`

#### Request Body (JSON)
*(Same shape as Create Post)*
```json
{
  "userId": "user-1234",
  "postId": 9999,
  "postType": 1,
  "imageUrl": "https://yourcdn.com/images/updated_face.jpg"
}
```

#### Response Body (HTTP 200 OK)
```json
{
  "isSuccess": true,
  "message": "Post successfully received and queued for matching."
}
```

---

### 2.3. Mark Post Resolved
Marks a post resolved, disabling active matching and purging biometric vector indices.
* **HTTP Method:** `POST`
* **URL:** `https://disparate-catcher-silenced.ngrok-free.dev/api/ai/posts/mark-resolved`

#### Request Body (JSON)
```json
{
  "userId": "user-1234",
  "postId": 9999
}
```

#### Response Body (HTTP 200 OK)
```json
{
  "isSuccess": true,
  "message": "Post 9999 marked as resolved, vector index cleaned."
}
```

---

### 2.4. Delete Post
Permanently deletes a post and purges it from database and vector indexes.
* **HTTP Method:** `DELETE`
* **URL:** `https://disparate-catcher-silenced.ngrok-free.dev/api/ai/posts`

#### Request Body (JSON)
```json
{
  "userId": "user-1234",
  "postId": 9999,
  "postType": 0,
  "imageUrl": "https://yourcdn.com/images/face_image.jpg"
}
```

#### Response Body (HTTP 200 OK)
```json
{
  "isSuccess": true,
  "message": "Post deleted successfully."
}
```

---

## 3. Webhook Callback (AI ➔ .NET Backend)
When matches are found, the AI background workers will call your `.NET` backend at the following endpoint.

* **Your Webhook Endpoint:** `POST https://mafqood.runasp.net/api/ai/match-results`
* **Authentication:** The AI engine will supply the `X-Api-Key: mafqood-shared-secret-key-2026` header to authorize the callback.

#### Callback Request Body (JSON)
```json
{
  "sourcePostId": 9999,
  "matches": [
    {
      "postId": 88712,
      "confidence": 0.942,
      "matchedImageUrl": "https://yourcdn.com/images/found_person_1.jpg"
    },
    {
      "postId": 88915,
      "confidence": 0.817,
      "matchedImageUrl": "https://yourcdn.com/images/found_person_2.jpg"
    }
  ]
}
```

#### Your Expected Response (HTTP 200 OK)
```json
{
  "isSuccess": true,
  "message": "Webhook results processed successfully."
}
```
