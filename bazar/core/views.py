from django.shortcuts import render
from inzeraty.models import Inzerat
# Create your views here.
def home(request):
    inzeraty = Inzerat.objects.all().order_by('-vytvorene')
    return render(request, 'home.html', {'inzeraty': inzeraty})