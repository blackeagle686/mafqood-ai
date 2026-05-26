"""
Serializers for the AI (LLM) endpoints.

Validates inputs for text moderation and entity extraction.
"""
from rest_framework import serializers


class ModerateTextSerializer(serializers.Serializer):
    """Input schema for the text content moderation endpoint."""

    text = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        help_text="Arabic or English text to classify for appropriateness.",
    )


class ExtractEntitiesSerializer(serializers.Serializer):
    """Input schema for the entity extraction (VLM) endpoint."""

    text = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        help_text="Raw Arabic/English social media post text to extract entities from.",
    )
    image_url = serializers.URLField(
        required=False,
        allow_null=True,
        default=None,
        help_text=(
            "Optional public URL of an image to pass to the VLM for visual context "
            "(e.g., clothing description, age estimation)."
        ),
    )


class MatchPostRequestSerializer(serializers.Serializer):
    """Input schema for connecting with the .NET backend post evaluation."""

    postId = serializers.IntegerField(
        required=True,
        help_text="The ID of the post in the .NET backend."
    )
    userId = serializers.CharField(
        required=True,
        help_text="The ID of the user who created the post."
    )
    imageUrl = serializers.CharField(
        required=True,
        help_text="The relative or absolute path/URL to the post image."
    )
    postType = serializers.IntegerField(
        required=True,
        help_text="0 for Lost (Missing), 1 for Found."
    )


class PostIntegrationSerializer(serializers.Serializer):
    """
    Serializer for the main Create, Update, and Delete post endpoints.
    """
    userId = serializers.CharField(
        required=True,
        help_text="The ID of the user who created the post."
    )
    postId = serializers.IntegerField(
        required=True,
        help_text="Unique post identifier in the Mafqood database."
    )
    postType = serializers.IntegerField(
        required=True,
        help_text="0 = Lost, 1 = Found."
    )
    imageUrl = serializers.CharField(
        required=True,
        help_text="Public URL or path of the item image."
    )

    def validate_postType(self, value):
        if value not in (0, 1):
            raise serializers.ValidationError("postType must be 0 (Lost) or 1 (Found).")
        return value


class MarkResolvedIntegrationSerializer(serializers.Serializer):
    """
    Serializer for marking a post as resolved.
    """
    userId = serializers.CharField(
        required=True,
        help_text="The ID of the user who created the post."
    )
    postId = serializers.IntegerField(
        required=True,
        help_text="Unique post identifier in the Mafqood database."
    )


class DNAProfileIntegrationSerializer(serializers.Serializer):
    """
    Serializer for creating or updating DNA profiles from the backend.
    """
    userId = serializers.CharField(
        required=True,
        help_text="The ID of the user who created the post."
    )
    postId = serializers.IntegerField(
        required=True,
        help_text="Unique post identifier in the Mafqood database."
    )
    postType = serializers.IntegerField(
        required=False,
        default=0,
        help_text="0 for Lost, 1 for Found."
    )
    strData = serializers.JSONField(
        required=True,
        help_text="Dictionary of STR loci mapped to list of alleles."
    )
    gender = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=10,
        help_text="XX, XY, etc."
    )


class DNASearchSerializer(serializers.Serializer):
    """
    Serializer for DNA search queries.
    """
    strData = serializers.JSONField(
        required=True,
        help_text="Dictionary of STR loci mapped to list of alleles."
    )
    searchType = serializers.ChoiceField(
        choices=["direct", "parent_child", "sibling"],
        default="direct",
        help_text="The relationship type to match against."
    )
    minOverlap = serializers.IntegerField(
        required=False,
        default=5,
        help_text="Minimum overlapping STR loci required for matching."
    )


