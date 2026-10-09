import io
import re
from PIL import Image, ImageOps, UnidentifiedImageError
from django import forms
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods, require_GET
from .models import UserProfile


class ProfileForm(forms.Form):
    mobile = forms.CharField(required=False, max_length=25, label='Mobile number', widget=forms.TextInput(attrs={'type':'tel', 'autocomplete':'tel'}))
    photo = forms.FileField(required=False, label='Profile picture', help_text='JPEG, PNG or WebP · Maximum 5 MB', widget=forms.FileInput(attrs={'accept':'image/jpeg,image/png,image/webp'}))
    remove_photo = forms.BooleanField(required=False, label='Remove current picture')

    def clean_mobile(self):
        value = self.cleaned_data['mobile'].strip()
        if value and (not re.fullmatch(r'\+?[0-9 ()-]+', value) or not 7 <= len(re.sub(r'\D', '', value)) <= 15):
            raise forms.ValidationError('Enter a valid mobile number with 7–15 digits, including country code if needed.')
        return value

    def clean_photo(self):
        upload = self.cleaned_data.get('photo')
        if not upload:
            return None
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Choose an image smaller than 5 MB.')
        try:
            with Image.open(upload) as picture:
                if picture.format not in {'JPEG','PNG','WEBP'} or picture.width * picture.height > 20000000:
                    raise ValueError()
                picture = ImageOps.exif_transpose(picture)
                picture = ImageOps.fit(picture.convert('RGB'), (256,256))
                output = io.BytesIO()
                picture.save(output, format='JPEG', quality=85)
                return output.getvalue()
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
            raise forms.ValidationError('Choose a valid JPEG, PNG or WebP image up to 20 megapixels.')


@login_required
@require_http_methods(['GET','POST'])
def account(request):
    profile = UserProfile.objects.filter(user=request.user).first()
    form = ProfileForm(initial={'mobile':profile.mobile if profile else ''})
    password_form = PasswordChangeForm(request.user)
    if request.method == 'POST':
        if request.POST.get('action') == 'password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password has been changed.')
                return redirect('profile')
        else:
            form = ProfileForm(request.POST, request.FILES)
            if form.is_valid():
                updates = {'mobile':form.cleaned_data['mobile']}
                if form.cleaned_data['photo']:
                    updates['photo'] = form.cleaned_data['photo']
                elif form.cleaned_data['remove_photo']:
                    updates['photo'] = None
                UserProfile.objects.update_or_create(user=request.user, defaults=updates)
                messages.success(request, 'Your profile has been updated.')
                return redirect('profile')
    return render(request, 'registration/profile.html', {'profile_form':form, 'password_form':password_form, 'has_photo':bool(profile and profile.photo)})


@login_required
@require_GET
def photo(request):
    profile = UserProfile.objects.filter(user=request.user).first()
    if not profile or not profile.photo:
        raise Http404()
    response = HttpResponse(bytes(profile.photo), content_type='image/jpeg')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
