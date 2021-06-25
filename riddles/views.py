import json
import numpy

from datetime import datetime
from django import forms
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.generic.edit import FormView
from django.views.generic.base import View
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth import login, logout
from django.utils.translation import gettext, gettext_lazy as _
from django.db.models import Avg

from .models import Riddle, Option, Message, Mark

app_url = "/riddles/"


def index(request):
    return HttpResponse("Hello, World!")


# главная страница со списком загадок
def index(request):
    message = None
    if "message" in request.GET:
        message = request.GET["message"]
    return render(
        request,
        "index.html",
        {
            "latest_riddles":
                Riddle.objects.order_by('-pub_date')[:5],
            "message": message
        }
    )


def admin(request):
    message = None
    if "message" in request.GET:
        message = request.GET["message"]
    # создание HTML-страницы по шаблону admin.html
    # с заданными параметрами latest_riddles и message
    return render(
        request,
        "admin.html",
        {
            "latest_riddles":
                Riddle.objects.order_by('-pub_date')[:5],
            "message": message,
        }
    )


# страница загадки со списком ответов
def detail(request, riddle_id):
    error_message = None
    if "error_message" in request.GET:
        error_message = request.GET["error_message"]
    # формируем список ответов
    ordered_option_set = \
        list(Option.objects.filter(riddle_id=riddle_id))
    # формируем случайный порядок номеров ответов
    option_iter = \
        numpy.random.permutation(len(ordered_option_set))
    # формируем новый список, в который выписываем ответы
    # в сформированном случайном порядке
    option_set = []
    for num in option_iter:
        option_set.append(ordered_option_set[num])
    return render(
        request,
        "answer.html",
        {
            # передаем список ответов в случайном порядке
            "option_set": option_set,

            "riddle": get_object_or_404(
                Riddle, pk=riddle_id),
            "error_message": error_message,
            "latest_messages":
                Message.objects
                    .filter(chat_id=riddle_id)
                    .order_by('-pub_date')[:5],
            # кол-во оценок, выставленных пользователем
            "already_rated_by_user":
                Mark.objects
                    .filter(author_id=request.user.id)
                    .filter(riddle_id=riddle_id)
                    .count(),
            # оценка текущего пользователя
            "user_rating":
                Mark.objects
                    .filter(author_id=request.user.id)
                    .filter(riddle_id=riddle_id)
                    .aggregate(Avg('mark'))
                    ["mark__avg"],
            # средняя по всем пользователям оценка
            "avg_mark":
                Mark.objects
                    .filter(riddle_id=riddle_id)
                    .aggregate(Avg('mark'))
                    ["mark__avg"]
        }
    )


def answer(request, riddle_id):
    riddle = get_object_or_404(Riddle, pk=riddle_id)
    try:
        option = riddle.option_set.get(pk=request.POST['option'])
    except (KeyError, Option.DoesNotExist):
        return redirect(
            '/riddles/' + str(riddle_id) +
            '?error_message=Option does not exist',
        )
    else:
        if option.correct:
            return redirect(
                "/riddles/?message=Nice! Choose another one!")
        else:
            return redirect(
                '/riddles/'+str(riddle_id)+
                '?error_message=Wrong Answer!',
            )


def post_mark(request, riddle_id):
    msg = Mark()
    msg.author = request.user
    msg.riddle = get_object_or_404(Riddle, pk=riddle_id)
    msg.mark = request.POST['mark']
    msg.pub_date = datetime.now()
    msg.save()
    return HttpResponseRedirect(app_url+str(riddle_id))


def post_riddle(request):
    # защита от добавления загадок неадминистраторами
    author = request.user
    if not (author.is_authenticated and author.is_staff):
        return HttpResponseRedirect(app_url+"admin")
    # добавление загадки
    rid = Riddle()
    rid.riddle_text = request.POST['text']
    rid.pub_date = datetime.now()
    rid.save()
    # добавление вариантов ответа
    i = 1    # нумерация вариантов на форме начинается с 1
    # количество вариантов неизвестно, поэтому ожидаем возникновение исключения,
    # когда варианты кончатся
    try:
        while request.POST['option'+str(i)]:
            opt = Option()
            opt.riddle = rid
            opt.text = request.POST['option'+str(i)]
            opt.correct = (i == 1)
            opt.save()
            i += 1
    except:
        pass

    for i in User.objects.all():
        # проверка, что текущий пользователь подписан - указал e-mail
        if i.email != '':
            send_mail(
                'New riddle',
                'A new riddle was added on riddles portal:\n' +
                'http://localhost:8000/riddles/' + str(rid.id) + '.',
                'savelyeva.noreply@gmail.com',
                # список получателей из одного получателя
                [i.email],
                # отключаем замалчивание ошибок
                False
            )

    return HttpResponseRedirect(app_url+str(rid.id))


def get_mark(request, riddle_id):
    res = Mark.objects\
            .filter(riddle_id=riddle_id)\
            .aggregate(Avg('mark'))

    return JsonResponse(json.dumps(res), safe=False)


def post(request, riddle_id):
    msg = Message()
    msg.author = request.user
    msg.chat = get_object_or_404(Riddle, pk=riddle_id)
    msg.message = request.POST['message']
    msg.pub_date = datetime.now()
    msg.save()
    return HttpResponseRedirect(app_url+str(riddle_id))


def msg_list(request, riddle_id):
    res = list(
            Message.objects
                .filter(chat_id=riddle_id)
                .order_by('-pub_date')[:5]
                .values('author__username',
                        'pub_date',
                        'message'
                )
            )
    for r in res:
        r['pub_date'] = \
            r['pub_date'].strftime(
                '%d.%m.%Y %H:%M:%S'
            )
    return JsonResponse(json.dumps(res), safe=False)


# функция для удаления подписки
def unsubscribe(request):
    request.user.email = ''
    request.user.save()
    return HttpResponseRedirect(app_url)


class RegisterFormView(FormView):
    form_class = UserCreationForm
    success_url = app_url + "login/"
    template_name = "reg/register.html"

    def form_valid(self, form):
        form.save()
        return super(RegisterFormView, self).form_valid(form)


class LoginFormView(FormView):
    form_class = AuthenticationForm
    template_name = "reg/login.html"
    success_url = app_url

    def form_valid(self, form):
        self.user = form.get_user()
        login(self.request, self.user)
        return super(LoginFormView, self).form_valid(form)


class LogoutView(View):
    def get(self, request):
        logout(request)
        return HttpResponseRedirect(app_url)


class PasswordChangeView(FormView):
    form_class = PasswordChangeForm
    template_name = 'reg/password_change_form.html'
    success_url = app_url + 'login/'

    def get_form_kwargs(self):
        kwargs = super(PasswordChangeView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        if self.request.method == 'POST':
            kwargs['data'] = self.request.POST
        return kwargs

    def form_valid(self, form):
        form.save()
        return super(PasswordChangeView, self).form_valid(form)


# класс, описывающий логику формы:
class SubscribeForm(forms.Form):
    # поле для ввода e-mail
    email = forms.EmailField(
        label=_("E-mail"),
        required=True,
    )

    # конструктор для запоминания пользователя, которому задается e-mail
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    # сохранение e-mail
    def save(self, commit=True):
        self.user.email = self.cleaned_data["email"]
        if commit:
            self.user.save()
        return self.user


# класс, описывающий взаимодействие логики
class SubscribeView(FormView):
    form_class = SubscribeForm
    template_name = 'subscribe.html'
    # после подписки возвращаем на главную станицу
    success_url = app_url

    # передача пользователя для конструктора класса с логикой
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    # вызов логики сохранения введенных данных
    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(self.success_url)


