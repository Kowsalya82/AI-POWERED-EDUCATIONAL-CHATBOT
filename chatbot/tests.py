from django.test import TestCase

# Create your tests here.
from django.test import TestCase
from .models import User

class UserModelTests(TestCase):

    def test_create_user(self):
        """Test if a user can be created successfully."""
        user = User.objects.create(
            full_name="Test User",
            username="testuser",
            email="testuser@example.com",
            password="testpass123",
            address="123 Test Street",
            phone="1234567890"
        )
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "testuser@example.com")



from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from .models import UploadedPDF, SearchHistory

class PDFUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.test_file = SimpleUploadedFile("test.pdf", b"Dummy file content", content_type="application/pdf")

    def test_upload_pdf(self):
        response = self.client.post(reverse('pdfs_view'), {'file': self.test_file, 'title': 'Test PDF'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UploadedPDF.objects.filter(title='Test PDF').exists())

    def test_delete_pdf(self):
        pdf = UploadedPDF.objects.create(title="To Delete", file="uploads/to_delete.pdf")
        response = self.client.post(reverse('pdfs_view'), {'delete': pdf.id})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UploadedPDF.objects.filter(id=pdf.id).exists())

class HistoryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.history_entry = SearchHistory.objects.create(user="testuser", query="What is AI?", response="AI is Artificial Intelligence.")

    def test_get_history(self):
        response = self.client.get(reverse('get_history'))
        self.assertEqual(response.status_code, 200)
        self.assertIn("What is AI?", response.json()['history'])

    def test_export_history(self):
        response = self.client.get(reverse('export_history'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')