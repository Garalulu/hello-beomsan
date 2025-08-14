import os
import uuid
import mimetypes
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError


class FileUploadHandler:
    """Handle file uploads for songs and background images"""
    
    ALLOWED_AUDIO_EXTENSIONS = ['.mp3', '.ogg', '.wav', '.m4a', '.flac']
    ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    
    MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @classmethod
    def validate_audio_file(cls, file):
        """Validate audio file"""
        # Check file extension
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in cls.ALLOWED_AUDIO_EXTENSIONS:
            raise ValidationError(f"Audio file must be one of: {', '.join(cls.ALLOWED_AUDIO_EXTENSIONS)}")
        
        # Check file size
        if file.size > cls.MAX_AUDIO_SIZE:
            raise ValidationError(f"Audio file too large. Maximum size: {cls.MAX_AUDIO_SIZE // (1024*1024)}MB")
        
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(file.name)
        if mime_type and not mime_type.startswith('audio/'):
            raise ValidationError("File is not a valid audio file")
    
    @classmethod
    def validate_image_file(cls, file):
        """Validate image file"""
        # Check file extension
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in cls.ALLOWED_IMAGE_EXTENSIONS:
            raise ValidationError(f"Image file must be one of: {', '.join(cls.ALLOWED_IMAGE_EXTENSIONS)}")
        
        # Check file size
        if file.size > cls.MAX_IMAGE_SIZE:
            raise ValidationError(f"Image file too large. Maximum size: {cls.MAX_IMAGE_SIZE // (1024*1024)}MB")
        
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(file.name)
        if mime_type and not mime_type.startswith('image/'):
            raise ValidationError("File is not a valid image file")
    
    @classmethod
    def generate_unique_filename(cls, original_filename, file_type='audio'):
        """Generate unique filename while preserving extension"""
        ext = os.path.splitext(original_filename)[1].lower()
        unique_id = str(uuid.uuid4())
        return f"{file_type}/{unique_id}{ext}"
    
    @classmethod
    def save_audio_file(cls, file, song_title=None):
        """Save audio file to Fly volume"""
        cls.validate_audio_file(file)
        
        # Generate unique filename
        filename = cls.generate_unique_filename(file.name, 'audio')
        
        # Save file
        filepath = default_storage.save(filename, file)
        
        return filepath
    
    @classmethod
    def save_image_file(cls, file, song_title=None):
        """Save image file to Fly volume"""
        cls.validate_image_file(file)
        
        # Generate unique filename
        filename = cls.generate_unique_filename(file.name, 'images')
        
        # Save file
        filepath = default_storage.save(filename, file)
        
        return filepath
    
    @classmethod
    def delete_file(cls, filepath):
        """Delete file from storage"""
        if filepath and default_storage.exists(filepath):
            default_storage.delete(filepath)
            return True
        return False
    
    @classmethod
    def get_file_url(cls, filepath):
        """Get URL for serving file"""
        if filepath and default_storage.exists(filepath):
            return default_storage.url(filepath)
        return None


class BulkFileProcessor:
    """Process multiple files for bulk song uploads"""
    
    @classmethod
    def process_directory(cls, directory_path, audio_extensions=None, image_extensions=None):
        """
        Process all files in a directory and return categorized file info.
        Used for bulk imports from Fly volume directories.
        """
        if audio_extensions is None:
            audio_extensions = FileUploadHandler.ALLOWED_AUDIO_EXTENSIONS
        if image_extensions is None:
            image_extensions = FileUploadHandler.ALLOWED_IMAGE_EXTENSIONS
        
        audio_files = []
        image_files = []
        
        if not os.path.exists(directory_path):
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()
                
                if file_ext in audio_extensions:
                    audio_files.append({
                        'filename': file,
                        'path': file_path,
                        'relative_path': os.path.relpath(file_path, directory_path),
                        'size': os.path.getsize(file_path)
                    })
                elif file_ext in image_extensions:
                    image_files.append({
                        'filename': file,
                        'path': file_path,
                        'relative_path': os.path.relpath(file_path, directory_path),
                        'size': os.path.getsize(file_path)
                    })
        
        return {
            'audio_files': audio_files,
            'image_files': image_files,
            'total_audio': len(audio_files),
            'total_images': len(image_files)
        }
    
    @classmethod
    def match_audio_with_images(cls, audio_files, image_files):
        """
        Try to match audio files with corresponding background images
        based on filename similarity.
        """
        matches = []
        
        for audio_file in audio_files:
            audio_name = os.path.splitext(audio_file['filename'])[0]
            
            # Look for exact match first
            matching_image = None
            for image_file in image_files:
                image_name = os.path.splitext(image_file['filename'])[0]
                if audio_name.lower() == image_name.lower():
                    matching_image = image_file
                    break
            
            # If no exact match, look for partial matches
            if not matching_image:
                for image_file in image_files:
                    image_name = os.path.splitext(image_file['filename'])[0]
                    if (audio_name.lower() in image_name.lower() or 
                        image_name.lower() in audio_name.lower()):
                        matching_image = image_file
                        break
            
            matches.append({
                'audio': audio_file,
                'image': matching_image,
                'suggested_title': audio_name.replace('_', ' ').replace('-', ' ').title()
            })
        
        return matches