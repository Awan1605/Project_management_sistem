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
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
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
            self.add_error('due_date', 'End Date must not exceed project ETD.')

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
