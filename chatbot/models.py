from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission

# Custom User Model

# User Model (Separate from Authentication Model)
class User(models.Model):
    full_name = models.CharField(max_length=255)
    username = models.CharField(max_length=255, unique=True)  # Prevent duplicate usernames
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)  # Consider hashing passwords
    address = models.TextField()
    phone = models.CharField(max_length=20)

    def __str__(self):
        return self.full_name
    
class SearchHistory(models.Model):
    email = models.EmailField(default='default@example.com') #add default value
    query = models.TextField()
    response = models.TextField()
    score = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField()

    def __str__(self):
        return f"{self.email} - {self.timestamp}"

class UploadedPDF(models.Model):
    subject = models.CharField(max_length=255)
    file_path = models.FileField(upload_to='uploads/') #example.
    thumb_path = models.ImageField(upload_to='thumbnails/', null=True, blank=True) #example.

    def __str__(self):
        return self.subject