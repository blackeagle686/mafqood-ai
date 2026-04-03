from rest_framework import serializers

class FaceSearchSerializer(serializers.Serializer):
    file = serializers.ImageField()
    n_results = serializers.IntegerField(default=5)
    use_age_progression = serializers.BooleanField(default=False)
