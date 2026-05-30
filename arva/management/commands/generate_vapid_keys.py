import base64

from django.core.management.base import BaseCommand, CommandError


def _b64url_no_pad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


class Command(BaseCommand):
    help = 'Generate VAPID public/private keypair for Web Push and print .env lines.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subject',
            default='mailto:support@example.com',
            help='VAPID subject claim (default: mailto:support@example.com)',
        )

    def handle(self, *args, **options):
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ec
        except Exception as exc:
            raise CommandError(
                'Missing dependency: cryptography. Install with: pip install cryptography'
            ) from exc

        private_key = ec.generate_private_key(ec.SECP256R1())
        private_numbers = private_key.private_numbers()
        private_bytes = private_numbers.private_value.to_bytes(32, 'big')

        public_key = private_key.public_key()
        public_numbers = public_key.public_numbers()
        x = public_numbers.x.to_bytes(32, 'big')
        y = public_numbers.y.to_bytes(32, 'big')
        uncompressed_public = b'\x04' + x + y

        public_b64 = _b64url_no_pad(uncompressed_public)
        private_b64 = _b64url_no_pad(private_bytes)
        subject = options.get('subject') or 'mailto:support@example.com'

        self.stdout.write(self.style.SUCCESS('VAPID keypair generated successfully.\n'))
        self.stdout.write('# Add these lines to your .env')
        self.stdout.write(f'WEBPUSH_VAPID_PUBLIC_KEY={public_b64}')
        self.stdout.write(f'WEBPUSH_VAPID_PRIVATE_KEY={private_b64}')
        self.stdout.write(f'WEBPUSH_VAPID_CLAIMS_SUBJECT={subject}')

