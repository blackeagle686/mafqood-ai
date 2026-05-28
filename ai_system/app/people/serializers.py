from rest_framework import serializers

class PersonReportSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    last_seen = serializers.CharField(max_length=255, required=False, allow_blank=True)
    details = serializers.CharField(required=False, allow_blank=True)
    age = serializers.IntegerField(required=False, allow_null=True)
    lat = serializers.FloatField(required=False, allow_null=True)
    long = serializers.FloatField(required=False, allow_null=True)
    dna_str_loci = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    file = serializers.ImageField() # Matches HTML name="file"
