"""
URL configuration for hello_beomsan project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from apps.tournament.views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name="home"),
    path('game/', include('apps.tournament.urls')),
    path('auth/', include('apps.accounts.urls')),
]
