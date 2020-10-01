import subprocess

import click

from .. import config as tutor_config
from .. import env as tutor_env
from .. import images
from .. import plugins

BASE_IMAGE_NAMES = ["openedx", "forum", "android"]
DEV_IMAGE_NAMES = ["openedx-dev"]


@click.group(name="images", short_help="Manage docker images")
def images_command():
    pass


@click.command(
    short_help="Build docker images",
    help="Build the docker images necessary for an Open edX platform.",
)
@click.argument("image", nargs=-1)
@click.option(
    "--no-cache", is_flag=True, help="Do not use cache when building the image"
)
@click.option(
    "-a",
    "--build-arg",
    "build_args",
    multiple=True,
    help="Set build-time docker ARGS in the form 'myarg=value'. This option may be specified multiple times.",
)
@click.option(
    "--add-host",
    "add_hosts",
    multiple=True,
    help="Set a custom host-to-IP mapping (host:ip).",
)
@click.pass_obj
def build(context, image, no_cache, build_args, add_hosts):
    config = tutor_config.load(context.root)
    command_args = []
    if no_cache:
        command_args.append("--no-cache")
    for build_arg in build_args:
        command_args += ["--build-arg", build_arg]
    for add_host in add_hosts:
        command_args += ["--add-host", add_host]
    for i in image:
        build_image(context.root, config, i, *command_args)


@click.command(short_help="Pull images from the Docker registry")
@click.argument("image", nargs=-1)
@click.pass_obj
def pull(context, image):
    config = tutor_config.load(context.root)
    for i in image:
        pull_image(config, i)


@click.command(short_help="Push images to the Docker registry")
@click.argument("image", nargs=-1)
@click.pass_obj
def push(context, image):
    config = tutor_config.load(context.root)
    for i in image:
        push_image(config, i)


def build_image(root, config, image, *args):
    # Build base images
    for img, tag in iter_images(config, image, BASE_IMAGE_NAMES):
        images.build(tutor_env.pathjoin(root, "build", img), tag, *args)

    # Build plugin images
    for plugin, img, tag in iter_plugin_images(config, image, "build-image"):
        images.build(
            tutor_env.pathjoin(root, "plugins", plugin, "build", img), tag, *args
        )

    # Build dev images with user id argument
    user_id = subprocess.check_output(["id", "-u"]).strip().decode()
    dev_build_arg = ["--build-arg", "USERID={}".format(user_id)]
    for img, tag in iter_images(config, image, DEV_IMAGE_NAMES):
        images.build(tutor_env.pathjoin(root, "build", img), tag, *dev_build_arg, *args)


def pull_image(config, image):
    for _img, tag in iter_images(config, image, image_names(config)):
        images.pull(tag)
    for _plugin, _img, tag in iter_plugin_images(config, image, "remote-image"):
        images.pull(tag)


def push_image(config, image):
    for _img, tag in iter_images(config, image, BASE_IMAGE_NAMES):
        images.push(tag)
    for _plugin, _img, tag in iter_plugin_images(config, image, "remote-image"):
        images.push(tag)


def iter_images(config, image, image_list):
    for img in image_list:
        if image in [img, "all"]:
            tag = images.get_tag(config, img)
            yield img, tag


def iter_plugin_images(config, image, hook_name):
    for plugin, hook in plugins.iter_hooks(config, hook_name):
        for img, tag in hook.items():
            if image in [img, "all"]:
                tag = tutor_env.render_str(config, tag)
                yield plugin, img, tag


def image_names(config):
    return BASE_IMAGE_NAMES + vendor_image_names(config)


def vendor_image_names(config):
    vendor_images = [
        "elasticsearch",
        "memcached",
        "mongodb",
        "mysql",
        "nginx",
        "rabbitmq",
        "smtp",
    ]
    for image in vendor_images[:]:
        if not config.get("ACTIVATE_" + image.upper(), True):
            vendor_images.remove(image)
    return vendor_images


images_command.add_command(build)
images_command.add_command(pull)
images_command.add_command(push)
