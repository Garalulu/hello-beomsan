"""
Admin views for song management
Handles upload, edit, delete, and bulk CSV operations for songs
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Q

from ..models import Song
from .utils import (
    validate_url, sanitize_input, convert_google_drive_url,
    clear_song_caches, check_duplicate_song
)

import csv
import io
import logging

logger = logging.getLogger(__name__)


@staff_member_required
@ensure_csrf_cookie
def upload_song(request):
    """Upload new song"""
    try:
        if request.method == 'POST':
            # Sanitize and validate inputs
            title = sanitize_input(request.POST.get('title', ''))
            original_song = sanitize_input(request.POST.get('original_song', ''))
            audio_url = request.POST.get('audio_url', '').strip()
            background_image_url = request.POST.get('background_image_url', '').strip()
            
            # Security validation
            if not validate_url(audio_url):
                messages.error(request, "Invalid or unauthorized audio URL domain.")
                return render(request, 'pages/admin/upload_song.html')
                
            if not validate_url(background_image_url):
                messages.error(request, "Invalid or unauthorized image URL domain.")
                return render(request, 'pages/admin/upload_song.html')
            
            # Basic validation
            if not title:
                messages.error(request, "Song title is required.")
            elif not audio_url:
                messages.error(request, "Audio URL is required.")
            else:
                # Check for duplicates
                is_duplicate, existing_song = check_duplicate_song(title, original_song)
                if is_duplicate:
                    if original_song:
                        messages.error(request, f"Song '{title}' (Original: {original_song}) already exists in the database.")
                    else:
                        messages.error(request, f"Song '{title}' already exists in the database.")
                else:
                    try:
                        # Convert Google Drive URLs to proper format
                        audio_url = convert_google_drive_url(audio_url, 'audio')
                        background_image_url = convert_google_drive_url(background_image_url, 'image')
                        
                        with transaction.atomic():
                            song = Song.objects.create(
                                title=title,
                                original_song=original_song,
                                audio_url=audio_url,
                                background_image_url=background_image_url
                            )
                        
                        # Clear relevant caches after adding new song
                        clear_song_caches()
                        
                        messages.success(request, f"Song '{title}' uploaded successfully!")
                        return redirect('manage_songs')
                        
                    except IntegrityError as e:
                        logger.error(f"Database integrity error creating song: {e}")
                        messages.error(request, "A song with this information already exists.")
                    except Exception as e:
                        logger.error(f"Error creating song: {e}")
                        messages.error(request, "An error occurred while uploading the song.")
        
        return render(request, 'pages/admin/upload_song.html')
        
    except Exception as e:
        logger.error(f"Error in upload_song view: {type(e).__name__}: {str(e)}")
        messages.error(request, "An error occurred. Please try again.")
        return redirect('manage_songs')


@staff_member_required
@ensure_csrf_cookie
def manage_songs(request):
    """Manage existing songs"""
    try:
        # Get search parameters
        search_query = request.GET.get('search', '').strip()
        
        songs = Song.objects.all().order_by('-created_at')
        
        # Apply search filter if provided
        if search_query:
            songs = songs.filter(
                Q(title__icontains=search_query) |
                Q(original_song__icontains=search_query)
            )
        
        # Pagination
        paginator = Paginator(songs, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        response = render(request, 'pages/admin/manage_songs.html', {
            'page_obj': page_obj,
            'search_query': search_query
        })
        # Add cache-busting headers to ensure fresh data
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
        
    except Exception as e:
        logger.error(f"Error in manage_songs view: {type(e).__name__}: {str(e)}")
        messages.error(request, "Unable to load songs management page.")
        response = render(request, 'pages/admin/manage_songs.html', {
            'page_obj': None,
            'search_query': ''
        })
        # Add cache-busting headers to ensure fresh data
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


@staff_member_required
@ensure_csrf_cookie
def edit_song(request, song_id):
    """Edit existing song"""
    song = get_object_or_404(Song, id=song_id)
    
    if request.method == 'POST':
        # Sanitize and validate inputs
        title = sanitize_input(request.POST.get('title', ''))
        original_song = sanitize_input(request.POST.get('original_song', ''))
        audio_url = request.POST.get('audio_url', '').strip()
        background_image_url = request.POST.get('background_image_url', '').strip()
        
        # Security validation
        if not validate_url(audio_url):
            messages.error(request, "Invalid or unauthorized audio URL domain.")
            return render(request, 'pages/admin/edit_song.html', {'song': song})
            
        if not validate_url(background_image_url):
            messages.error(request, "Invalid or unauthorized image URL domain.")
            return render(request, 'pages/admin/edit_song.html', {'song': song})
        
        if title and audio_url:
            # Check for duplicates only if title or original_song changed
            if song.title != title or song.original_song != original_song:
                is_duplicate, existing_song = check_duplicate_song(title, original_song)
                if is_duplicate and existing_song.id != song.id:
                    if original_song:
                        messages.error(request, f"Song '{title}' (Original: {original_song}) already exists in the database.")
                    else:
                        messages.error(request, f"Song '{title}' already exists in the database.")
                    return render(request, 'pages/admin/edit_song.html', {'song': song})
            
            # Convert Google Drive URLs to proper format
            audio_url = convert_google_drive_url(audio_url, 'audio')
            background_image_url = convert_google_drive_url(background_image_url, 'image')
            
            song.title = title
            song.original_song = original_song
            song.audio_url = audio_url
            song.background_image_url = background_image_url
            song.save()
            
            # Clear relevant caches after updating song
            clear_song_caches()
            
            messages.success(request, f"Song '{title}' updated successfully!")
            return redirect('manage_songs')
        else:
            messages.error(request, "Title and audio URL are required.")
    
    return render(request, 'pages/admin/edit_song.html', {'song': song})


@staff_member_required
@require_POST
def delete_song(request, song_id):
    """Delete existing song"""
    try:
        song = get_object_or_404(Song, id=song_id)
        title = song.title
        song.delete()
        
        # Clear relevant caches
        clear_song_caches()
        
        logger.info(f"Song '{title}' deleted by {request.user.username}")
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({
                'success': True,
                'message': f"Song '{title}' deleted successfully!"
            })
        else:
            messages.success(request, f"Song '{title}' deleted successfully!")
            response = redirect('manage_songs')
            # Add cache-busting headers to force refresh
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response
            
    except Exception as e:
        logger.error(f"Error deleting song {song_id}: {e}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({
                'success': False,
                'error': f"Error deleting song: {str(e)}"
            })
        else:
            messages.error(request, f"Error deleting song: {str(e)}")
            response = redirect('manage_songs')
            # Add cache-busting headers to force refresh
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response


@staff_member_required
@ensure_csrf_cookie
def upload_csv(request):
    """Bulk upload songs from CSV file"""
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            messages.error(request, "Please select a CSV file to upload.")
            return render(request, 'pages/admin/upload_csv.html')
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "File must be a CSV file.")
            return render(request, 'pages/admin/upload_csv.html')
        
        try:
            # Read CSV file with robust parsing for Google Sheets exports
            file_data = csv_file.read().decode('utf-8')
            csv_data = io.StringIO(file_data)
            
            # Try to detect the CSV format
            sample = file_data[:1024]
            sniffer = csv.Sniffer()
            
            try:
                # Try to detect the dialect
                dialect = sniffer.sniff(sample, delimiters=',')
                csv_data.seek(0)
                reader = csv.DictReader(csv_data, dialect=dialect)
            except csv.Error:
                # If dialect detection fails, use a flexible approach
                csv_data.seek(0)
                # Use QUOTE_MINIMAL which handles unquoted fields better
                reader = csv.DictReader(csv_data, 
                                      quoting=csv.QUOTE_MINIMAL,
                                      skipinitialspace=True)
            
            # Validate required columns
            required_columns = ['title', 'audio_url']
            fieldnames = reader.fieldnames or []
            
            # Log detected fieldnames for debugging
            logger.info(f"CSV upload - Detected columns: {fieldnames}")
            
            if not all(col in fieldnames for col in required_columns):
                missing_cols = [col for col in required_columns if col not in fieldnames]
                available_cols = ', '.join(fieldnames) if fieldnames else 'None detected'
                messages.error(request, 
                              f"CSV must contain columns: {', '.join(required_columns)}. "
                              f"Missing: {', '.join(missing_cols)}. "
                              f"Available columns: {available_cols}. "
                              f"Optional: original_song, background_image_url")
                return render(request, 'pages/admin/upload_csv.html')
            
            # Process rows
            created_count = 0
            error_count = 0
            errors = []
            processed_songs = set()  # Track songs in this CSV to prevent within-file duplicates
            
            with transaction.atomic():
                for row_num, row in enumerate(reader, start=2):  # Start at 2 since row 1 is headers
                    title = row.get('title', '').strip()
                    original_song = row.get('original_song', '').strip()
                    audio_url = row.get('audio_url', '').strip()
                    background_image_url = row.get('background_image_url', '').strip()
                    
                    # Validate required fields
                    if not title:
                        errors.append(f"Row {row_num}: Missing title")
                        error_count += 1
                        continue
                    
                    if not audio_url:
                        errors.append(f"Row {row_num}: Missing audio_url")
                        error_count += 1
                        continue
                    
                    try:
                        # Create a key for tracking duplicates within this CSV
                        song_key = (title.lower(), original_song.lower())
                        
                        # Check for duplicates within this CSV file
                        if song_key in processed_songs:
                            if original_song:
                                errors.append(f"Row {row_num}: '{title}' (Original: {original_song}) - Duplicate within this CSV file")
                            else:
                                errors.append(f"Row {row_num}: '{title}' - Duplicate within this CSV file")
                            error_count += 1
                            continue
                        
                        # Check for duplicates in existing database
                        is_duplicate, existing_song = check_duplicate_song(title, original_song)
                        if is_duplicate:
                            if original_song:
                                errors.append(f"Row {row_num}: '{title}' (Original: {original_song}) - Song already exists in database")
                            else:
                                errors.append(f"Row {row_num}: '{title}' - Song already exists in database")
                            error_count += 1
                            continue
                        
                        # Convert Google Drive URLs to proper format
                        audio_url = convert_google_drive_url(audio_url, 'audio')
                        background_image_url = convert_google_drive_url(background_image_url, 'image')
                        
                        # Create song
                        song = Song.objects.create(
                            title=title,
                            original_song=original_song,
                            audio_url=audio_url,
                            background_image_url=background_image_url
                        )
                        
                        # Mark this song as processed to prevent duplicates within this CSV
                        processed_songs.add(song_key)
                        created_count += 1
                        
                    except IntegrityError as e:
                        errors.append(f"Row {row_num}: {title} - Database error (possibly duplicate)")
                        error_count += 1
                    except Exception as e:
                        errors.append(f"Row {row_num}: {title} - {str(e)}")
                        error_count += 1
            
            # Clear relevant caches if songs were added
            if created_count > 0:
                clear_song_caches()
            
            # Show results
            if created_count > 0:
                messages.success(request, f"Successfully uploaded {created_count} songs.")
            
            if error_count > 0:
                # Categorize errors for better reporting
                duplicate_errors = [e for e in errors if 'Duplicate' in e or 'already exists' in e]
                other_errors = [e for e in errors if e not in duplicate_errors]
                
                if duplicate_errors:
                    dup_count = len(duplicate_errors)
                    dup_msg = f"Skipped {dup_count} duplicate song(s)."
                    if dup_count <= 5:
                        dup_msg += " " + "; ".join(duplicate_errors)
                    else:
                        dup_msg += f" First 5: " + "; ".join(duplicate_errors[:5])
                    messages.warning(request, dup_msg)
                
                if other_errors:
                    error_msg = f"Failed to upload {len(other_errors)} song(s) due to errors."
                    if len(other_errors) <= 5:
                        error_msg += " Errors: " + "; ".join(other_errors)
                    else:
                        error_msg += f" First 5 errors: " + "; ".join(other_errors[:5])
                    messages.error(request, error_msg)
            
            if created_count > 0:
                return redirect('manage_songs')
                
        except UnicodeDecodeError as e:
            logger.error(f"CSV file encoding error: {e}")
            messages.error(request, "Error reading CSV file. Please ensure the file is saved as UTF-8 encoding.")
        except csv.Error as e:
            logger.error(f"CSV parsing error: {e}")
            messages.error(request, f"Error parsing CSV file: {str(e)}. Please check the file format and ensure proper CSV structure.")
        except Exception as e:
            logger.error(f"Error processing CSV upload: {e}")
            messages.error(request, f"Error processing CSV file: {str(e)}")
    
    return render(request, 'pages/admin/upload_csv.html')