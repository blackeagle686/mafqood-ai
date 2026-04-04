from rest_framework import serializers

class FaceSearchSerializer(serializers.Serializer):
    file = serializers.FileField()
    n_results = serializers.IntegerField(default=5)
    use_age_progression = serializers.BooleanField(default=False)
    sampling_rate = serializers.IntegerField(default=15, min_value=1)
