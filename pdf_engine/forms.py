from django import forms

# ================= Split PDF Form =================
class SplitPDFForm(forms.Form):
    pdf_file = forms.FileField(label="Select PDF")
    split_mode = forms.ChoiceField(
        choices=[('fixed', 'Fixed Ranges'), ('custom', 'Custom Ranges')],
        label="Split Mode"
    )
    range_size = forms.IntegerField(
        required=False,
        min_value=1,
        label="Pages per Split (for Fixed Mode)",
        widget=forms.NumberInput(attrs={'placeholder': 'e.g., 5'})
    )
    custom_ranges = forms.CharField(
        required=False,
        label="Custom Ranges (for Custom Mode)",
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 1-3,5,7'})
    )

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get('split_mode')
        range_size = cleaned_data.get('range_size')
        custom_ranges = cleaned_data.get('custom_ranges')

        if mode == 'fixed' and not range_size:
            self.add_error('range_size', 'Range size is required for Fixed Ranges mode.')
        elif mode == 'custom' and not custom_ranges:
            self.add_error('custom_ranges', 'Custom ranges are required for Custom Ranges mode.')


# ================= Merge PDF Form =================
class MergePDFForm(forms.Form):
    pdf_files = forms.FileField(
        required=True,
        label="Select PDF files"
    )
    # NOTE: Multiple files handled in the view, not by Django field


# ================= Compress PDF Form =================
class CompressPDFForm(forms.Form):
    pdf_file = forms.FileField(label="Select PDF")
    compression_level = forms.ChoiceField(
        choices=[
            ('extreme', 'Extreme Compression'),
            ('recommended', 'Recommended Compression'),
            ('less', 'Less Compression')
        ],
        label="Compression Level"
    )
