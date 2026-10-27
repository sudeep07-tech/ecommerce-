from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["reviewer_name", "rating", "comment"]

        widgets = {
            "reviewer_name": forms.TextInput(attrs={
                "class": "review-input",
                "placeholder": "Enter your name",
            }),
            "rating": forms.RadioSelect(
                choices=[
                    (1, "1 Star"),
                    (2, "2 Stars"),
                    (3, "3 Stars"),
                    (4, "4 Stars"),
                    (5, "5 Stars"),
                ],
                attrs={"class": "star-radio"},
            ),
            "comment": forms.Textarea(attrs={
                "class": "review-input",
                "placeholder": "Write your review here...",
                "rows": 5,
            }),
        }
