import json
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        # This function is called just before the social login process is
        # completed. We're using it to link existing users and to correctly
        # handle the extra_data field for our custom model.

        # Keep a reference to the data from the social provider.
        extra_data = sociallogin.account.extra_data

        if sociallogin.is_existing:
            # If the social account already exists, just update the extra_data
            # by serializing it to a string for our TextField.
            sociallogin.account.extra_data = json.dumps(extra_data)
            return

        # For new logins, check if a local user with this email already exists.
        if 'email' in extra_data:
            try:
                email = extra_data['email'].lower()
                user = User.objects.get(email=email)
                # If a user is found, connect the social account to them.
                sociallogin.connect(request, user)
            except User.DoesNotExist:
                # If no user is found, the regular signup process will continue.
                pass
        
        # Finally, serialize the extra_data to a string so it can be saved
        # in our custom model's TextField. This avoids the JSON_VALID error.
        sociallogin.account.extra_data = json.dumps(extra_data) 