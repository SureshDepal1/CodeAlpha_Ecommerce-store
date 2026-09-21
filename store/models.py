from django.db import models
from django.contrib.auth.models import User


class Product(models.Model):
	name = models.CharField(max_length=200)
	description = models.TextField()
	price = models.DecimalField(max_digits=10, decimal_places=2)
	image = models.ImageField(upload_to="products/", blank=True, null=True)
	category = models.CharField(max_length=100)
	stock = models.PositiveIntegerField(default=0)
	is_available = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return self.name


class Order(models.Model):
	class Status(models.TextChoices):
		PENDING = "pending", "Pending"
		CONFIRMED = "confirmed", "Confirmed"
		PROCESSING = "processing", "Processing"
		SHIPPED = "shipped", "Shipped"
		DELIVERED = "delivered", "Delivered"
		CANCELLED = "cancelled", "Cancelled"

	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
	full_name = models.CharField(max_length=200)
	email = models.EmailField()
	phone = models.CharField(max_length=30)
	address = models.TextField()
	city = models.CharField(max_length=100)
	state = models.CharField(max_length=100, blank=True)
	postal_code = models.CharField(max_length=20)
	country = models.CharField(max_length=100)
	total_amount = models.DecimalField(max_digits=12, decimal_places=2)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"Order #{self.pk} - {self.full_name}"


class OrderItem(models.Model):
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
	product = models.ForeignKey(
		Product,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="order_items",
	)
	product_name = models.CharField(max_length=255)
	price = models.DecimalField(max_digits=12, decimal_places=2)
	quantity = models.PositiveIntegerField()
	subtotal = models.DecimalField(max_digits=12, decimal_places=2)

	def __str__(self):
		return f"{self.product_name} x {self.quantity}"


class EmailVerification(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="email_verification")
	code_hash = models.CharField(max_length=128)
	created_at = models.DateTimeField(auto_now_add=True)
	code_sent_at = models.DateTimeField()
	expires_at = models.DateTimeField()
	attempts = models.PositiveSmallIntegerField(default=0)
	send_count = models.PositiveSmallIntegerField(default=1)
	verified_at = models.DateTimeField(null=True, blank=True)

	def __str__(self):
		return f"Email verification for {self.user.username}"
