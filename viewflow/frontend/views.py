from __future__ import unicode_literals

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.http import is_safe_url
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.views import generic

from ..flow.views.mixins import FlowListMixin
from ..models import Task
from ..utils import get_flow_namespace


class BaseTasksActionView(FlowListMixin, generic.TemplateView):
    action_name = None
    success_url = 'viewflow:index'
    template_name = 'viewflow/site_task_action.html'

    def get_context_data(self, **kwargs):
        context = super(BaseTasksActionView, self).get_context_data(**kwargs)
        context['tasks'] = self.tasks
        return context

    def get_success_url(self):
        if 'back' in self.request.GET:
            back_url = self.request.GET['back']
            if not is_safe_url(url=back_url, host=self.request.get_host()):
                back_url = '/'
            return back_url

        return reverse(self.success_url)

    def get_tasks(self, user, task_pks):
        raise NotImplementedError

    def report(self, message, level=messages.INFO, fail_silently=True, **kwargs):

        tasks_links = []
        for task in self.tasks:
            namespace = get_flow_namespace(
                task.flow_task.flow_class, self.request.resolver_match.namespace, self.ns_map)
            task_url = task.flow_task.get_task_url(
                task, url_type='detail', user=self.request.user, namespace=namespace)
            task_link = '<a href="{task_url}">#{task_pk}</a>'.format(
                task_url=task_url,
                task_pk=task.pk)
            tasks_links.append(task_link)

        kwargs.update({
            'tasks': ' '.join(tasks_links)
        })

        message = mark_safe(_(message).format(**kwargs))

        messages.add_message(self.request, level, message, fail_silently=fail_silently)

    def success(self, message, fail_silently=True, **kwargs):
        self.report(message, level=messages.SUCCESS, fail_silently=fail_silently, **kwargs)

    def error(self, message, fail_silently=True, **kwargs):
        self.report(message, level=messages.ERROR, fail_silently=fail_silently, **kwargs)

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        requested_pks = [pk for pk in request.GET.get('tasks', '').split(',') if pk.isdigit()]
        self.tasks = self.get_tasks(request.user, requested_pks)

        return super(BaseTasksActionView, self).dispatch(request, *args, **kwargs)


class TasksUnAssignView(BaseTasksActionView):
    action_name = 'unassign'

    def get_tasks(self, user, tasks_pks):
        return Task.objects.inbox(self.flows, user).filter(pk__in=tasks_pks)

    def post(self, request, *args, **kwargs):
        for task in self.tasks:
            lock = task.process.flow_class.lock_impl(task.process.flow_class.instance)
            with lock(task.process.flow_class, task.process_id):
                activation = task.activate()
                activation.unassign()
        self.success(_('Tasks {tasks} has been unassigned.'))
        return HttpResponseRedirect(self.get_success_url())


class TasksAssignView(BaseTasksActionView):
    action_name = 'assign'
    success_url = 'viewflow:queue'

    def get_tasks(self, user, tasks_pks):
        return Task.objects.queue(self.flows, user).filter(pk__in=tasks_pks)

    def post(self, request, *args, **kwargs):
        for task in self.tasks:
            lock = task.process.flow_class.lock_impl(task.process.flow_class.instance)
            with lock(task.process.flow_class, task.process_id):
                activation = task.activate()
                activation.assign(self.request.user)

        self.success(_('Tasks {tasks} has been assigned.'))
        return HttpResponseRedirect(self.get_success_url())
