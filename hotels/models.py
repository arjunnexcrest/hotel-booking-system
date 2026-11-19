from django.db import models
from django.conf import settings
from django.utils.text import slugify
from core.models import TimeStampedModel


class Hotel(TimeStampedModel):
    """
    Hotel registration, onboarding status and profile information.
    """
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Approval'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        SUSPENDED = 'SUSPENDED', 'Suspended'

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_hotels'
    )
    description = models.TextField(blank=True)
    hotel_type = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='India')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    star_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    check_in_time = models.TimeField(default='14:00', null=True, blank=True)
    check_out_time = models.TimeField(default='11:00', null=True, blank=True)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING_APPROVAL,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'hotels'
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['city']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'hotel'
            slug = base_slug
            counter = 1
            while Hotel.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class HotelImage(TimeStampedModel):
    """
    Images gallery for a registered hotel.
    """
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='hotels/images/')
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = 'hotel_images'

    def __str__(self):
        return f"Image for {self.hotel.name}"


class HotelDocument(TimeStampedModel):
    """
    Verification documents uploaded by hotel owners for super-admin verification.
    """
    class DocumentType(models.TextChoices):
        BUSINESS_LICENSE = 'BUSINESS_LICENSE', 'Business License'
        IDENTITY_PROOF = 'IDENTITY_PROOF', 'Identity Proof'
        TAX_ID = 'TAX_ID', 'Tax ID / GST'
        HYGIENE_CERT = 'HYGIENE_CERT', 'Hygiene / Food Safety Certificate'
        OTHER = 'OTHER', 'Other Verification Document'

    class VerificationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    file = models.FileField(upload_to='hotels/documents/')
    status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    rejection_reason = models.TextField(blank=True)

    class Meta:
        db_table = 'hotel_documents'

    def __str__(self):
        return f"{self.get_document_type_display()} for {self.hotel.name}"


class HotelApproval(TimeStampedModel):
    """
    Audit log of approval, review, and rejection decisions by super-admins.
    """
    class Decision(models.TextChoices):
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='approval_history')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='hotel_reviews'
    )
    decision = models.CharField(max_length=30, choices=Decision.choices)
    reason = models.TextField(blank=True)

    class Meta:
        db_table = 'hotel_approvals'
        indexes = [
            models.Index(fields=['hotel', 'decision']),
        ]

    def __str__(self):
        return f"{self.hotel.name} - {self.get_decision_display()}"
