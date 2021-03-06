import auditor


class AuditorMixinView(object):
    get_event = None
    update_event = None
    delete_event = None

    def get_object(self):
        instance = super().get_object()
        method = self.request.method.lower()
        if method == 'get':
            auditor.record(event_type=self.get_event,
                           instance=instance,
                           actor_id=self.request.user.id,
                           actor_name=self.request.user.username)
        elif method == 'delete':
            auditor.record(event_type=self.delete_event,
                           instance=instance,
                           actor_id=self.request.user.id,
                           actor_name=self.request.user.username)
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        auditor.record(event_type=self.update_event,
                       instance=instance,
                       actor_id=self.request.user.id,
                       actor_name=self.request.user.username)
