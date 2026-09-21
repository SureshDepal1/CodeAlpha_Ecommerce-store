from django.contrib import admin
from django.utils import timezone

from .models import EmailVerification, Order, OrderItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
	list_display = ("name", "category", "price", "stock", "is_available", "created_at")
	list_filter = ("category", "is_available")
	search_fields = ("name", "category")


class OrderItemInline(admin.TabularInline):
	model = OrderItem
	extra = 0
	fields = ("product", "product_name", "price", "quantity", "subtotal")
	readonly_fields = ("product_name", "price", "quantity", "subtotal")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ("id", "user", "full_name", "email", "total_amount", "status", "payment_method", "payment_status", "created_at")
	list_filter = ("status", "payment_method", "payment_status", "created_at")
	search_fields = ("user__username", "email", "full_name")
	ordering = ("-created_at",)
	inlines = (OrderItemInline,)
	actions = ("mark_selected_as_paid", "mark_selected_as_unpaid")

	@admin.action(description="Mark selected orders as paid")
	def mark_selected_as_paid(self, request, queryset):
		queryset.update(payment_status="paid", paid_at=timezone.now())

	@admin.action(description="Mark selected orders as unpaid")
	def mark_selected_as_unpaid(self, request, queryset):
		queryset.update(payment_status="unpaid", paid_at=None)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
	list_display = ("order", "product_name", "price", "quantity", "subtotal")
	search_fields = ("product_name", "order__email")


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
	list_display = ("user", "code_sent_at", "expires_at", "attempts", "send_count", "verified_at")
	readonly_fields = ("user", "created_at", "code_sent_at", "expires_at", "attempts", "send_count", "verified_at")
	fields = readonly_fields
	search_fields = ("user__username", "user__email")
