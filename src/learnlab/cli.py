from __future__ import annotations

from collections.abc import Callable

import typer

from learnlab.config import Settings, load_settings
from learnlab.errors import ConfigurationError, LearnLabError
from learnlab.providers.base import Provider
from learnlab.providers.registry import build_provider

ProviderFactory = Callable[[Settings, str], Provider]

app = typer.Typer()
provider_app = typer.Typer()
app.add_typer(provider_app, name="provider")
provider_factory: ProviderFactory = build_provider


@provider_app.command("test")
def provider_test(profile_name: str) -> None:
    """Check the configured provider profile without changing infrastructure."""
    try:
        settings = load_settings()
        profile = settings.provider(profile_name)
        typer.echo(f"Provider profile: {profile_name}")
        if not profile.tls_verify:
            typer.echo("WARNING: TLS certificate verification is disabled")
        provider = provider_factory(settings, profile_name)
        health = provider.health_check()
    except LearnLabError as error:
        typer.echo(f"Error: {error}")
        raise typer.Exit(
            code=2 if isinstance(error, ConfigurationError) else 3
        ) from None

    for check in health.checks:
        status = "PASS" if check.ok else "FAIL"
        typer.echo(f"{status} {check.name}: {check.detail}")
    for warning in health.warnings:
        typer.echo(f"WARNING: {warning}")
    if any(check.required and not check.ok for check in health.checks):
        raise typer.Exit(code=1)
