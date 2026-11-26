from rest_framework import serializers
from .models import IDCardTemplate, IDCardBatch

class IDCardTemplateSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    school_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    clear_front_template = serializers.BooleanField(write_only=True, required=False, default=False)
    clear_back_template = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = IDCardTemplate
        fields = [
            'id', 'school', 'school_id', 'school_name', 'name', 'layout', 'primary_color', 'secondary_color',
            'header_background', 'front_template', 'back_template', 'front_svg_content', 'back_svg_content',
            'field_mappings', 'clear_front_template', 'clear_back_template',
            'show_blood_group', 'show_emergency_contact',
            'show_barcode', 'show_address', 'is_default', 'created_at'
        ]
        read_only_fields = ['id', 'school', 'created_at']

    def to_internal_value(self, data):
        # Leave valid JSON strings intact for DRF JSONField; only normalize empty multipart strings
        if hasattr(data, 'copy') and data.get('field_mappings') == '':
            mutable = data.copy()
            mutable['field_mappings'] = '{}'
            return super().to_internal_value(mutable)
        return super().to_internal_value(data)

    def create(self, validated_data):
        school_id = validated_data.pop('school_id', None)
        clear_front = validated_data.pop('clear_front_template', False)
        clear_back = validated_data.pop('clear_back_template', False)
        if clear_front:
            validated_data['front_template'] = None
            validated_data['front_svg_content'] = ''
        if clear_back:
            validated_data['back_template'] = None
            validated_data['back_svg_content'] = ''
        if school_id:
            from apps.schools.models import School
            validated_data['school'] = School.objects.filter(id=school_id).first()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        school_id = validated_data.pop('school_id', None)
        clear_front = validated_data.pop('clear_front_template', False)
        clear_back = validated_data.pop('clear_back_template', False)
        if clear_front:
            if instance.front_template:
                instance.front_template.delete(save=False)
            validated_data['front_template'] = None
            validated_data['front_svg_content'] = ''
        if clear_back:
            if instance.back_template:
                instance.back_template.delete(save=False)
            validated_data['back_template'] = None
            validated_data['back_svg_content'] = ''
        if school_id is not None:
            if school_id:
                from apps.schools.models import School
                validated_data['school'] = School.objects.filter(id=school_id).first()
            else:
                validated_data['school'] = None
        return super().update(instance, validated_data)

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
