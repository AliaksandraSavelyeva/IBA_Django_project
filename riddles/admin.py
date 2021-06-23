from django.contrib import admin

from .models import Option, Riddle, Message, Mark

admin.site.register(Riddle)
admin.site.register(Option)
admin.site.register(Message)
admin.site.register(Mark)

