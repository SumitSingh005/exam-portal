from .models import PortalSettings


def portal_settings(request):
    settings_obj = PortalSettings.get_solo()
    return {
        'portal_settings': settings_obj,
        'site_name': settings_obj.site_name,
        'support_email': settings_obj.support_email,
    }
