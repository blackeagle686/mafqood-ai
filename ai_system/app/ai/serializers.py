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
