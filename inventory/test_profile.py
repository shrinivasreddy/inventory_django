import io
from PIL import Image
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import UserProfile

class ProfileTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('profile-user',password='OldSafe!12345')
        self.client.force_login(self.user)
    def test_profile_photo_and_isolation(self):
        stream=io.BytesIO();Image.new('RGB',(400,300),'blue').save(stream,format='PNG')
        response=self.client.post('/profile/',{'mobile':'+1 555 123 4567','photo':SimpleUploadedFile('photo.png',stream.getvalue(),content_type='image/png')})
        self.assertEqual(response.status_code,302)
        profile=UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.mobile,'+1 555 123 4567')
        self.assertEqual(Image.open(io.BytesIO(profile.photo)).size,(256,256))
        self.assertEqual(self.client.get('/profile/photo/').status_code,200)
        other=get_user_model().objects.create_user('other-profile')
        self.client.force_login(other)
        self.assertEqual(self.client.get('/profile/photo/').status_code,404)
        self.assertEqual(Client().get('/profile/').status_code,302)
    def test_invalid_upload_mobile_and_csrf(self):
        response=self.client.post('/profile/',{'mobile':'abc','photo':SimpleUploadedFile('bad.png',b'not image')})
        self.assertEqual(response.status_code,200)
        self.assertFalse(UserProfile.objects.exists())
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post('/profile/',{'mobile':'1234567890'}).status_code,403)
    def test_password_requires_old_password_and_preserves_session(self):
        data={'action':'password','old_password':'wrong','new_password1':'NewUnique!847394','new_password2':'NewUnique!847394'}
        self.assertEqual(self.client.post('/profile/',data).status_code,200)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('OldSafe!12345'))
        data['old_password']='OldSafe!12345'
        self.assertEqual(self.client.post('/profile/',data).status_code,302)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('NewUnique!847394'))
        self.assertEqual(self.client.get('/profile/').status_code,200)
