from django.contrib import admin

from .models import Order, OrderItem, Product


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
	list_display = ("id", "user", "full_name", "email", "total_amount", "status", "created_at")
	list_filter = ("status", "created_at")
	search_fields = ("user__username", "email", "full_name")
	ordering = ("-created_at",)
	inlines = (OrderItemInline,)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
	list_display = ("order", "product_name", "price", "quantity", "subtotal")
	search_fields = ("product_name", "order__email")
