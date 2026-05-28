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
    
    # Person Identifier Fields
    name = models.CharField(max_length=255, null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    dna_str_loci = models.JSONField(null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    long = models.FloatField(null=True, blank=True)
    video_url = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"

    def __str__(self):
        post_type_str = "Lost" if self.post_type == 0 else "Found"
        status_str = "Resolved" if self.is_resolved else "Active"
        return f"Post {self.post_id} ({post_type_str}) by User {self.user_id} - {status_str}"


class DNAProfile(models.Model):
    """
    Stores an STR DNA profile associated with a Post.
    """
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name='dna_profile')
    str_data = models.JSONField(help_text="STR loci keys mapped to list of alleles.")
    gender = models.CharField(max_length=10, blank=True, null=True, help_text="XX, XY, etc.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "DNA Profile"
        verbose_name_plural = "DNA Profiles"

    def __str__(self):
        return f"DNA Profile for Post {self.post.post_id}"


class DNAMatch(models.Model):
    """
    Records high-confidence DNA matches (Direct or Kinship).
    """
    MATCH_TYPES = [
        ('direct', 'Direct (Identical Person)'),
        ('kinship_parent_child', 'Parent-Child Relation'),
        ('kinship_sibling', 'Sibling Relation'),
    ]
    
    missing_post_id = models.IntegerField(db_index=True)
    found_post_id = models.IntegerField(db_index=True)
    match_type = models.CharField(max_length=30, choices=MATCH_TYPES)
    overlap_loci_count = models.IntegerField()
    matching_loci_count = models.IntegerField()
    confidence_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('missing_post_id', 'found_post_id')
        verbose_name = "DNA Match"
        verbose_name_plural = "DNA Matches"

    def __str__(self):
        return f"DNA Match: Missing {self.missing_post_id} <-> Found {self.found_post_id} (Type: {self.match_type}, Score: {self.confidence_score:.2f})"


