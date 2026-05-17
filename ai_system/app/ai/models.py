from django.db import models

class FaceMatch(models.Model):
    """
    Model to store and deduplicate face matches between missing and found posts.
    """
    missing_post_id = models.IntegerField(db_index=True)
    found_post_id = models.IntegerField(db_index=True)
    combined_score = models.FloatField()
    face_similarity = models.FloatField()
    time_score = models.FloatField()
    location_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent duplicate entries for the same pair of posts
        unique_together = ('missing_post_id', 'found_post_id')
        verbose_name = "Face Match"
        verbose_name_plural = "Face Matches"

    def __str__(self):
        return f"Match: Missing {self.missing_post_id} <-> Found {self.found_post_id} (Score: {self.combined_score:.2f})"


class Post(models.Model):
    """
    Model to track post lifecycles (active/deleted/resolved) from the .NET backend.
    """
    post_id = models.IntegerField(primary_key=True) # Unique postId from Mafqood
    user_id = models.CharField(max_length=255)
    post_type = models.IntegerField() # 0 = Lost, 1 = Found
    image_url = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"

    def __str__(self):
        post_type_str = "Lost" if self.post_type == 0 else "Found"
        status_str = "Resolved" if self.is_resolved else "Active"
        return f"Post {self.post_id} ({post_type_str}) by User {self.user_id} - {status_str}"

