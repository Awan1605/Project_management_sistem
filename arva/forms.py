"""
Form Arviga Project Manager
==========================
Mendefinisikan seluruh form yang digunakan di aplikasi:
- WebsiteSettingsForm: Pengaturan website
- RegisterForm: Registrasi user baru
- ProjectForm: CRUD project
- SubProjectForm: CRUD sub-project
- TaskForm: CRUD task
- CommentForm: Komentar pada task
- AttachmentForm: Lampiran file
- TaskListForm: CRUD task list
- ChecklistItemForm: Item checklist
- ProjectMemberForm: Keanggotaan project
- CreateUserInlineForm: Buat user oleh admin
- UserEditForm: Edit user oleh admin
- AdminPasswordResetForm: Reset password user
- AvatarUploadForm: Upload avatar
"""

import os
from html.parser import HTMLParser
from django import forms
from django.utils.html import escape
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from .models import (
    Project, SubProject, Task, Comment, Attachment,
    Label, TaskList, ChecklistItem, ProjectMember,
    UserProfile, WebsiteSettings
)

# Pilihan warna cover task
TASK_COVER_COLORS = [
    ('', 'No Cover'),
    ('primary', 'Blue'),
    ('success', 'Green'),
    ('danger', 'Red'),
    ('warning', 'Yellow'),
    ('info', 'Teal'),
    ('dark', 'Dark'),
]


class _RichTextSanitizer(HTMLParser):
    allowed_tags = {'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li', 'a'}
    void_tags = {'br'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.open_tags = []

    def _sanitize_href(self, href):
        href = (href or '').strip()
        if not href:
            return ''
        if href.startswith(('http://', 'https://', 'mailto:')):
            return href
        if href.startswith('//'):
            return f'https:{href}'
        if href.startswith('/'):
            return href
        if '://' not in href:
            return f'https://{href}'
        return ''

    def _normalize_tag(self, tag):
        t = (tag or '').lower()
        if t == 'div':
            return 'p'
        return t

    def handle_starttag(self, tag, attrs):
        t = self._normalize_tag(tag)
        if t not in self.allowed_tags:
            return
        if t == 'a':
            href = ''
            for key, val in attrs:
                if (key or '').lower() == 'href':
                    href = self._sanitize_href(val)
                    break
            if not href:
                return
            self.parts.append(f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer nofollow">')
            self.open_tags.append('a')
            return
        self.parts.append(f'<{t}>')
        if t not in self.void_tags:
            self.open_tags.append(t)

    def handle_endtag(self, tag):
        t = self._normalize_tag(tag)
        if t in self.void_tags or t not in self.allowed_tags:
            return
        for idx in range(len(self.open_tags) - 1, -1, -1):
            if self.open_tags[idx] == t:
                del self.open_tags[idx]
                self.parts.append(f'</{t}>')
                break

    def handle_data(self, data):
        if data:
            self.parts.append(escape(data))

    def get_html(self):
        while self.open_tags:
            t = self.open_tags.pop()
            self.parts.append(f'</{t}>')
        return ''.join(self.parts)


def sanitize_rich_text_html(value):
    raw = (value or '').strip()
    if not raw:
        return ''
    parser = _RichTextSanitizer()
    parser.feed(raw)
    parser.close()
    return parser.get_html()

class WebsiteSettingsForm(forms.ModelForm):
    """Form untuk mengubah pengaturan website global."""
    class Meta:
        model = WebsiteSettings
        fields = [
            'site_name',
            'logo',
            'favicon',
            'primary_color',
            'theme_mode',
            'navbar_bg',
            'body_bg',
            'text_color',
            'footer_text',
            'support_email',
            'maintenance_mode',
            'custom_css',
        ]
        widgets = {
            'site_name': forms.TextInput(attrs={'class': 'form-control'}),
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'navbar_bg': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'body_bg': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'text_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'footer_text': forms.TextInput(attrs={'class': 'form-control'}),
            'support_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'theme_mode': forms.Select(attrs={'class': 'form-select'}),
            'custom_css': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
        }


class AvatarUploadForm(forms.ModelForm):
    ICON_CHOICES = [
        (filename, filename)
        for filename in os.listdir("static/arva/img/profile")
        if filename.endswith((".png", ".jpg"))
    ]

    avatar_icon = forms.ChoiceField(
        choices=[("", "— Upload File Instead —")] + ICON_CHOICES,
        required=False
    )

    class Meta:
        model = UserProfile
        fields = ["avatar", "avatar_icon"]
        widgets = {
            "avatar": forms.FileInput(attrs={"class": "form-control"}),
        }

class CreateUserInlineForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username sudah digunakan.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email sudah terdaftar.")
        return email

class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'is_active', 'is_staff']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_username(self):
        username = self.cleaned_data['username']
        qs = User.objects.filter(username=username).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Username sudah digunakan.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if email:
            qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Email sudah digunakan.")
        return email


class UserProfileEditForm(forms.ModelForm):
    """Form untuk user edit profile sendiri (tanpa is_active, is_staff)"""
    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_username(self):
        username = self.cleaned_data['username']
        qs = User.objects.filter(username=username).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Username sudah digunakan.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if email:
            qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Email sudah digunakan.")
        return email


class MyProfileUpdateForm(forms.Form):
    full_name = forms.CharField(max_length=150, required=False)
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    avatar = forms.ImageField(required=False)
    avatar_icon = forms.ChoiceField(required=False, choices=())

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        icon_choices = [
            (filename, filename)
            for filename in os.listdir("static/arva/img/profile")
            if filename.endswith((".png", ".jpg", ".jpeg", ".webp"))
        ]
        self.fields['avatar_icon'].choices = [("", "No icon selected")] + icon_choices

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError('Username is required.')
        qs = User.objects.filter(username=username)
        if self.user:
            qs = qs.exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError('Username is already in use.')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        qs = User.objects.filter(email=email)
        if self.user:
            qs = qs.exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError('Email is already in use.')
        return email

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if not avatar:
            return avatar
        if avatar.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Avatar file size must be 2 MB or less.')
        content_type = (getattr(avatar, 'content_type', '') or '').lower()
        allowed = {'image/png', 'image/jpeg', 'image/webp'}
        if content_type not in allowed:
            raise forms.ValidationError('Avatar must be PNG, JPG, or WEBP.')
        return avatar

    def clean_avatar_icon(self):
        value = (self.cleaned_data.get('avatar_icon') or '').strip()
        if not value:
            return ''
        valid = {c[0] for c in self.fields['avatar_icon'].choices if c[0]}
        if value not in valid:
            raise forms.ValidationError('Selected avatar icon is invalid.')
        return value


class MyPasswordChangeForm(forms.Form):
    current_password = forms.CharField(required=True, widget=forms.PasswordInput())
    new_password = forms.CharField(required=True, widget=forms.PasswordInput())
    confirm_password = forms.CharField(required=True, widget=forms.PasswordInput())

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        value = self.cleaned_data.get('current_password') or ''
        if self.user and not self.user.check_password(value):
            raise forms.ValidationError('Current password is invalid.')
        return value

    def clean(self):
        cleaned = super().clean()
        new_password = cleaned.get('new_password') or ''
        confirm_password = cleaned.get('confirm_password') or ''
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', 'Password confirmation does not match.')
        if self.user and new_password:
            validate_password(new_password, self.user)
        return cleaned


class AdminPasswordResetForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="New Password"
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirm Password"
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('password_confirm')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Password konfirmasi tidak sama.")
        return cleaned

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class ProjectForm(forms.ModelForm):
    shared_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
        help_text="Only used for private projects. Selected users get project access."
    )
    shared_role = forms.ChoiceField(
        choices=((ProjectMember.ROLE_MEMBER, 'Member'),),
        required=False,
        initial=ProjectMember.ROLE_MEMBER,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Project sharing role is unified."
    )

    class Meta:
        model = Project
        fields = [
            'name', 'description', 'is_private', 'is_project', 'priority',
            'pm_assignee', 'start_date', 'start_date_tbd', 'etd',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control'}),
            'is_private': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_project': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'pm_assignee': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_date_tbd': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'etd': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        self.fields['shared_users'].queryset = User.objects.all().order_by('username')
        self.fields['pm_assignee'].queryset = User.objects.all().order_by('username')
        self.fields['pm_assignee'].required = False
        if current_user and current_user.is_authenticated:
            self.fields['shared_users'].queryset = self.fields['shared_users'].queryset.exclude(id=current_user.id)

    def clean(self):
        cleaned_data = super().clean()
        is_project = cleaned_data.get('is_project')
        start_date = cleaned_data.get('start_date')
        start_date_tbd = cleaned_data.get('start_date_tbd')
        etd = cleaned_data.get('etd')

        if is_project:
            if not start_date and not start_date_tbd:
                self.add_error('start_date', 'Start Date is required or mark it as TBD.')
                self.add_error('start_date_tbd', 'Mark Start Date as TBD if date is unknown.')
            if not etd:
                self.add_error('etd', 'ETD is required when Is Project is enabled.')
        if start_date and start_date_tbd:
            self.add_error('start_date_tbd', 'Choose either Start Date or TBD, not both.')
        if start_date and etd and etd < start_date:
            self.add_error('etd', 'ETD cannot be earlier than Start Date.')

        return cleaned_data

    def clean_description(self):
        return sanitize_rich_text_html(self.cleaned_data.get('description'))

class SubProjectForm(forms.ModelForm):
    class Meta:
        model = SubProject
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control'}),
        }

class TaskForm(forms.ModelForm):
    assignees = forms.ModelMultipleChoiceField(
        queryset=User.objects.all().order_by('username'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=False,
    )
    labels = forms.ModelMultipleChoiceField(
        queryset=Label.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=False,
    )
    cover_color = forms.ChoiceField(
        choices=TASK_COVER_COLORS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=Task.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'priority', 'status', 'start_date',
            'start_date_tbd', 'due_date', 'assignees', 'labels', 'cover_color'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_date_tbd': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        self.fields['priority'].choices = (
            (Task.PRIORITY_P0, 'P0 - Urgent'),
            (Task.PRIORITY_P1, 'P1 - High'),
            (Task.PRIORITY_P2, 'P2 - Medium'),
            (Task.PRIORITY_P3, 'P3 - Low'),
            (Task.PRIORITY_P4, 'P4 - Very Low'),
        )
        self.fields['status'].initial = Task.STATUS_NONE

    def clean(self):
        cleaned_data = super().clean()
        project = self.project
        if not project or not project.is_project:
            return cleaned_data

        title = (cleaned_data.get('title') or '').strip()
        assignees = cleaned_data.get('assignees')
        start_date = cleaned_data.get('start_date')
        start_date_tbd = cleaned_data.get('start_date_tbd')
        end_date = cleaned_data.get('due_date')
        priority = cleaned_data.get('priority')
        status = cleaned_data.get('status')

        if not title:
            self.add_error('title', 'Task Name is required.')
        if not assignees or assignees.count() == 0:
            self.add_error('assignees', 'Assignee is required.')
        elif assignees.count() > 1:
            self.add_error('assignees', 'Only one assignee is allowed for project tasks.')

        if not start_date and not start_date_tbd:
            self.add_error('start_date', 'Start Date is required or mark it as TBD.')
            self.add_error('start_date_tbd', 'Mark Start Date as TBD if date is unknown.')
        if start_date and start_date_tbd:
            self.add_error('start_date_tbd', 'Choose either Start Date or TBD, not both.')

        if not end_date:
            self.add_error('due_date', 'End Date is required.')
        if start_date and end_date and end_date < start_date:
            self.add_error('due_date', 'End Date cannot be earlier than Start Date.')
        if project.etd and end_date and end_date > project.etd:
            etd_display = project.etd.strftime('%B %d, %Y')
            self.add_error('due_date', f'Task End Date must be on or before the Project ETD ({etd_display}).')

        if priority not in {Task.PRIORITY_P0, Task.PRIORITY_P1, Task.PRIORITY_P2, Task.PRIORITY_P3, Task.PRIORITY_P4}:
            self.add_error('priority', 'Priority is required.')

        if status not in {Task.STATUS_NONE, Task.STATUS_IN_PROGRESS, Task.STATUS_DONE, Task.STATUS_INFEASIBLE}:
            self.add_error('status', 'Status is required.')

        return cleaned_data

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']

class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ['file']

class TaskListForm(forms.ModelForm):
    class Meta:
        model = TaskList
        fields = ['name']

class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ['content']

class ProjectMemberForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True
    )

    class Meta:
        model = ProjectMember
        fields = ['user', 'role']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }
