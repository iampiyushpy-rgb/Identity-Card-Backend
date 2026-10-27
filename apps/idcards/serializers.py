from rest_framework import serializers
from .models import IDCardTemplate, IDCardBatch

class IDCardTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = IDCardTemplate
        fields = [
            'id', 'school', 'name', 'layout', 'primary_color', 'secondary_color',
            'header_background', 'show_blood_group', 'show_emergency_contact',
            'show_barcode', 'show_address', 'is_default', 'created_at'
        ]
        read_only_fields = ['id', 'school', 'created_at']

class IDCardBatchSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    session_name = serializers.CharField(source='session.name', read_only=True)
    class_name = serializers.CharField(source='class_level.name', read_only=True)
    section_name = serializers.CharField(source='section.name', read_only=True)

    class Meta:
        model = IDCardBatch
        fields = [
            'id', 'school', 'template', 'template_name',
            'session', 'session_name', 'class_level', 'class_name',
            'section', 'section_name', 'total_cards', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'school', 'created_at']
