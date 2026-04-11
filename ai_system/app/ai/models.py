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
