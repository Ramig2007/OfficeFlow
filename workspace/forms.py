from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.text import slugify

from django.utils import timezone

from workspace.models import Booking, Room, User


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Логин")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label="Электронная почта", required=True)
    first_name = forms.CharField(label="Имя", max_length=150)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Адрес уже используется.")
        return email


class BookingForm(forms.Form):
    room = forms.ModelChoiceField(label="Переговорная", queryset=Room.objects.filter(is_active=True))
    title = forms.CharField(label="Тема встречи", max_length=140)
    starts_at = forms.SplitDateTimeField(
        label="Начало", input_date_formats=["%Y-%m-%d"], input_time_formats=["%H:%M"],
        widget=forms.SplitDateTimeWidget(date_attrs={"type": "date"}, time_attrs={"type": "time", "step": 3600}),
    )
    ends_at = forms.SplitDateTimeField(
        label="Окончание", input_date_formats=["%Y-%m-%d"], input_time_formats=["%H:%M"],
        widget=forms.SplitDateTimeWidget(date_attrs={"type": "date"}, time_attrs={"type": "time", "step": 3600}),
    )
    notes = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["room"].queryset = Room.objects.filter(is_active=True)


class RoomForm(forms.ModelForm):
    def clean_is_vip(self):
        new_value = self.cleaned_data["is_vip"]
        if self.instance.pk and new_value != self.instance.is_vip:
            if Booking.objects.filter(
                room=self.instance, status__in=Booking.ACTIVE_STATUSES,
                starts_at__gte=timezone.now(),
            ).exists():
                raise forms.ValidationError(
                    "Нельзя сменить VIP-статус при наличии будущих активных бронирований."
                )
        return new_value

    class Meta:
        model = Room
        fields = ["name", "floor", "location", "capacity", "description", "equipment", "is_vip", "is_active"]
        labels = {
            "name": "Название", "floor": "Этаж", "location": "Расположение", "capacity": "Вместимость",
            "description": "Описание", "equipment": "Оборудование", "is_vip": "VIP-переговорная",
            "is_active": "Доступна для бронирования",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def save(self, commit=True):
        room = super().save(commit=False)
        if not room.slug:
            base = slugify(room.name, allow_unicode=True) or "room"
            slug = base
            suffix = 2
            while Room.objects.exclude(pk=room.pk).filter(slug=slug).exists():
                slug = f"{base}-{suffix}"
                suffix += 1
            room.slug = slug
        if commit:
            room.save()
        return room


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "department"]
        labels = {"first_name": "Имя", "last_name": "Фамилия", "email": "Почта", "department": "Отдел"}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("Адрес уже используется.")
        return email
