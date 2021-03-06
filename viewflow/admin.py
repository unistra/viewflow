from django.contrib import admin, auth
from viewflow.models import Process, Task


class TaskInline(admin.TabularInline):
    model = Task
    fields = ['flow_task', 'flow_task_type', 'status',
              'token', 'owner']
    readonly_fields = ['flow_task', 'flow_task_type', 'status', 'token']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ProcessAdmin(admin.ModelAdmin):
    """
    List all of viewflow process
    """
    icon = '<i class="material-icons">assignment</i>'

    actions = None
    date_hierarchy = 'created'
    list_display = ['pk', 'created', 'flow_class', 'status', 'participants']
    list_display_links = ['pk', 'created', 'flow_class']
    list_filter = ['status']
    readonly_fields = ['flow_class', 'status', 'finished']
    inlines = [TaskInline]

    def has_add_permission(self, request):
        return False

    def participants(self, obj):
        user_ids = obj.task_set.exclude(owner__isnull=True).values('owner')
        USER_MODEL = auth.get_user_model()
        username_field = USER_MODEL.USERNAME_FIELD
        users = USER_MODEL._default_manager.filter(pk__in=user_ids).values_list(username_field)
        return ', '.join(user[0] for user in users)


class TaskAdmin(admin.ModelAdmin):
    """
    List all of viewflow tasks
    """
    icon = '<i class="material-icons">assignment_turned_in</i>'

    actions = None
    date_hierarchy = 'created'
    list_display = ['pk', 'created', 'process', 'status',
                    'owner', 'owner_permission', 'token',
                    'started', 'finished']
    list_display_links = ['pk', 'created', 'process']
    list_filter = ['status']
    readonly_fields = ['process', 'status', 'flow_task', 'started', 'finished', 'previous', 'token']

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        result = super(TaskAdmin, self).save_model(request, obj, form, change)

        status_action = next((action[len('_change_status_'):]
                              for action in request.POST.keys()
                              if action.startswith('_change_status_')), None)
        if status_action:
            activation = obj.activate()
            activation_class = activation.__class__
            transition = next((transition for transition in activation_class.status.get_available_transtions(activation)
                               if transition.name == status_action), None)
            if transition:
                transition(activation)
                request.POST['_continue'] = True

        return result


admin.site.register(Process, ProcessAdmin)
admin.site.register(Task, TaskAdmin)
