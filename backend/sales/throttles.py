from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class PublicLeadThrottle(AnonRateThrottle):
    scope = "public_leads"


class UserLeadsThrottle(UserRateThrottle):
    scope = "user_leads"
