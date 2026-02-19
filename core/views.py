from django.http import JsonResponse
from django.shortcuts import render


def health_check(request):
    return JsonResponse({"status": "ok"})


def home(request):
    return render(request, "home.html")
