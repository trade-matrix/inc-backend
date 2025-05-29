import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from accounts.models import Customer # Ensure 'accounts' is in INSTALLED_APPS and Customer model is correct
from django.utils.dateparse import parse_datetime
from django.db import IntegrityError

# Helper function to convert 'True'/'False' string to boolean
def to_bool(value_str):
    if isinstance(value_str, str):
        return value_str.lower() == 'true'
    return False # Default for None, empty string, or non-string

# Helper function to parse datetime strings, handling empty values
def parse_datetime_safe(datetime_str):
    if datetime_str and datetime_str.strip():
        dt = parse_datetime(datetime_str)
        return dt
    return None

class Command(BaseCommand):
    help = 'Imports users from a CSV file (static/users.csv) into the Customer model. Skips users if phone number or username already exists.'

    def handle(self, *args, **options):
        # Construct the full path to the CSV file
        # Assumes 'static' directory is at the project root (settings.BASE_DIR)
        csv_file_path = os.path.join(settings.BASE_DIR, 'static', 'users.csv')

        if not os.path.exists(csv_file_path):
            self.stderr.write(self.style.ERROR(f"CSV file not found at {csv_file_path}."))
            self.stderr.write(self.style.ERROR("Please ensure 'static/users.csv' exists relative to your project root (manage.py location)."))
            return # Exit if file not found

        users_imported_count = 0
        users_skipped_count = 0

        self.stdout.write(f"Starting user import from {csv_file_path}...")

        try:
            with open(csv_file_path, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                if not reader.fieldnames:
                    self.stderr.write(self.style.ERROR(f"CSV file at {csv_file_path} is empty or has no header row."))
                    return

                # Verify necessary columns exist
                # CSV columns: id,password,last_login,is_superuser,email,user_name,mobile,is_active,is_staff,created,updated,verified
                required_cols = ['mobile', 'user_name', 'password', 'created'] # 'created' for date_joined
                missing_cols = [col for col in required_cols if col not in reader.fieldnames]
                if missing_cols:
                    self.stderr.write(self.style.ERROR(f"CSV file is missing required columns: {', '.join(missing_cols)}"))
                    return

                for row_num, row in enumerate(reader, 2): # Start row_num from 2 (1 for header, 1 for first data row)
                    phone_number = row.get('mobile', '').strip()
                    username = row.get('user_name', '').strip()
                    password = row.get('password', '').strip() # Password should not be empty

                    if not phone_number:
                        self.stdout.write(self.style.WARNING(f"Row {row_num}: Skipping due to missing 'mobile' (phone number)."))
                        users_skipped_count += 1
                        continue

                    if not username:
                        self.stdout.write(self.style.WARNING(f"Row {row_num}: Skipping user with phone {phone_number} due to missing 'user_name'."))
                        users_skipped_count += 1
                        continue
                    
                    if not password:
                        self.stdout.write(self.style.WARNING(f"Row {row_num}: Skipping user {username} ({phone_number}) due to missing 'password'."))
                        users_skipped_count += 1
                        continue

                    # Check for existing user by phone number
                    if Customer.objects.filter(phone_number=phone_number).exists():
                        self.stdout.write(self.style.NOTICE(f"Row {row_num}: User with phone number {phone_number} already exists. Skipping."))
                        users_skipped_count += 1
                        continue
                    
                    # Check for existing user by username (as it's unique)
                    if Customer.objects.filter(username=username).exists():
                        self.stdout.write(self.style.WARNING(f"Row {row_num}: User with username '{username}' already exists (attempted phone: {phone_number}). Skipping."))
                        users_skipped_count += 1
                        continue

                    user_data = {
                        'username': username,
                        'password': password, # Password is pre-hashed
                        'email': row.get('email', '').strip() or None, # Allow empty email to become None
                        'phone_number': phone_number,
                        
                        'is_superuser': to_bool(row.get('is_superuser')),
                        'is_staff': to_bool(row.get('is_staff')),
                        'is_active': to_bool(row.get('is_active', 'True')), # Default to True if missing in CSV
                        
                        'verified': to_bool(row.get('verified')), # From Customer model
                        
                        'last_login': parse_datetime_safe(row.get('last_login')),
                        'date_joined': parse_datetime_safe(row.get('created')), # Map CSV 'created' to 'date_joined'
                    }
                    
                    # If date_joined is None from CSV, Django's default (timezone.now) will be used.
                    if user_data['date_joined'] is None:
                         self.stdout.write(self.style.WARNING(f"Row {row_num}: 'created' field (for date_joined) is missing or invalid for user {username}. Django will use current time."))
                         # We still pass it as None, Customer.objects.create will handle default.

                    try:
                        Customer.objects.create(**user_data)
                        users_imported_count += 1
                        self.stdout.write(self.style.SUCCESS(f"Row {row_num}: Successfully imported user: {username} ({phone_number})"))
                    except IntegrityError as e:
                        self.stdout.write(self.style.ERROR(f"Row {row_num}: Integrity error for user {username} ({phone_number}): {e}. This could be a duplicate username/phone if checks missed, or other DB constraint."))
                        users_skipped_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Row {row_num}: Error importing user {username} ({phone_number}): {e}"))
                        self.stdout.write(self.style.ERROR(f"Problematic data: { {k:v for k,v in row.items() if k in ['user_name', 'mobile', 'email']} }"))
                        users_skipped_count += 1
            
            self.stdout.write(self.style.SUCCESS(f"\\nImport process finished."))
            self.stdout.write(self.style.SUCCESS(f"Successfully imported: {users_imported_count} users."))
            self.stdout.write(self.style.WARNING(f"Skipped: {users_skipped_count} users."))

        except FileNotFoundError: # Should be caught by pre-check, but good practice
            self.stderr.write(self.style.ERROR(f"Critical: CSV file not found at {csv_file_path} during operation."))
        except Exception as e:
            # Catch any other unexpected errors during file processing or setup
            self.stderr.write(self.style.ERROR(f"An unexpected error occurred during the import process: {e}"))
            import traceback
            self.stderr.write(self.style.ERROR(traceback.format_exc()))
