from rest_framework import serializers

class PersonReportSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    last_seen = serializers.CharField(max_length=255, required=False, allow_blank=True)
    details = serializers.CharField(required=False, allow_blank=True)
    file = serializers.ImageField() # Matches HTML name="file"
