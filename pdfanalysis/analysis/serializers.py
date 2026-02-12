from rest_framework import serializers

class QARequestSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=1000)

class QASourceSerializer(serializers.Serializer):
    chunk_index = serializers.IntegerField()
    page_start = serializers.IntegerField()
    page_end = serializers.IntegerField()

class QAResponseSerializer(serializers.Serializer):
    status = serializers.IntegerField()
    answer = serializers.CharField()
    sources = QASourceSerializer(many=True)
