import json, codecs
from html import escape
from config import Config
from instagram_private_api import Client, errors
from pyrogram import Client as PyClient
from pyrogram import filters
from pyrogram.types import Message
from os import path
from asyncio import sleep


def to_json(python_object):
    if isinstance(python_object, bytes):
        return {'__class__': 'bytes',
                '__value__': codecs.encode(python_object, 'base64').decode()}
    raise TypeError(repr(python_object) + ' is not JSON serializable')


def from_json(json_object):
    if '__class__' in json_object and json_object['__class__'] == 'bytes':
        return codecs.decode(json_object['__value__'].encode(), 'base64')
    return json_object


def onlogin_callback(api, new_settings_file):
    cache_settings = api.settings
    with open(new_settings_file, 'w') as outfile:
        json.dump(cache_settings, outfile, default=to_json)
        print('SAVED: {0!s}'.format(new_settings_file))


try:
    if path.isfile('settings.json'):
        with open('settings.json', 'r') as file_data:
            cached_settings = json.load(file_data, object_hook=from_json)
            device_id = cached_settings.get('device_id')
            api = Client(Config.USERNAME, Config.PASSWORD, settings=cached_settings)
    else:
        api = Client(Config.USERNAME, Config.PASSWORD, on_login=lambda x: onlogin_callback(x, 'settings.json'))
except (errors.ClientCookieExpiredError, errors.ClientLoginRequiredError) as e:
    print('ClientCookieExpiredError/ClientLoginRequiredError: {0!s}'.format(e))
    api = Client(Config.USERNAME, Config.PASSWORD, device_id=device_id,
                 on_login=lambda x: onlogin_callback(x, 'settings.json'))
except errors.ClientLoginError as e:
    print('ClientLoginError {0!s}'.format(e))
    exit(9)
except errors.ClientError as e:
    print('ClientError {0!s} (Code: {1:d}, Response: {2!s})'.format(e.msg, e.code, e.error_response))
    exit(9)
except Exception as e:
    print('Unexpected Exception: {0!s}'.format(e))
    exit(99)

app = PyClient('bot', Config.API_ID, Config.API_HASH, bot_token=Config.BOT_TOKEN, **Config.DEVICE_INFO)


@app.on_message(filters.user(Config.SUDO) & filters.text & filters.regex(r'/user ([a-zA-Z0-9\._]+)$'))
async def get_user(_, msg: Message):
    username = msg.matches[0].group(1)
    msg2 = await msg.reply_text('لطفا صبر کنید...')
    try:
        info = api.username_info(username)
        caption = f'<b>Followers</b> : <code>{info["user"]["follower_count"]}</code>\n' \
                  f'<b>Followings</b> : <code>{info["user"]["following_count"]}</code>\n' \
                  f'<b>Posts</b> : <code>{info["user"]["media_count"]}</code>\n' \
                  f'<b>Private</b> : <code>{info["user"]["is_private"]}</code>\n' \
                  f'<b>Name</b> : <code>{escape(info["user"]["full_name"])}</code>\n'
        await msg2.reply_photo(info['user']['profile_pic_url'], caption=caption)
    except errors.ClientError as e:
        err = json.loads(e.error_response)
        await msg2.edit_text(f'<b>ClientError</b>\nCode : <code>{e.code}</code>\n<i>{e.msg}</i>')
        await msg2.reply_text('\n'.join([f'<b>{i}</b> : {err[i]}' for i in err]))
    except Exception as e:
        await msg2.edit_text(str(e))


@app.on_message(filters.user(Config.SUDO) & filters.text & filters.regex(r'/follow ([a-zA-Z0-9\._]+)$'))
async def follow(_, msg: Message):
    if not Config.FOLLOWING:
        Config.FOLLOWING = True
        username = msg.matches[0].group(1)
        msg2 = await msg.reply_text('لطفا صبر کنید...')
        try:
            user = api.username_info(username)
            assert user['user']['follower_count'] > 0, 'این کاربر فالور ندارد.'
            assert not user['user']['is_private'], 'این بیج خصوصی می باشد.'
            await msg2.edit_text(f'در حال دریافت لیست فالور ها...')
            followers = api.user_followers(user['user']['pk'], api.generate_uuid())
            n = 0
            txt = ''
            for i in followers['users'][:70]:
                
                result = api.friendships_create(i['pk'])
                print(result)
                assert result['status'] == 'ok', result['status']
                n += 1
                txt += i['username'] + '\n'
                if n % Config.CN_FOLLOW == 0:
                    await msg2.edit_text(
                        '10  کابر آخر فالو شده تا کنون :' + f'\n<code>{txt}</code>' + f'کل کاربران فالو شده تا کنون {n}' + '\nبقیه عملیات تا یک ساعت دیگر...'
                        )
                    txt = ''
                    await sleep(3600)
                    msg2 = await msg2.reply_text('ادامه عملیات..')
                else:
                    await msg2.edit_text('درحال فالو کردن'
                                         f'\nکاربران فالو شده : {n}')
                    await sleep(3)
            await msg2.reply_text('عملیات فالو به پایان رسید')
        except errors.ClientError as e:
            err = json.loads(e.error_response)
            await msg2.edit_text(f'<b>ClientError</b>\nCode : <code>{e.code}</code>\n<i>{e.msg}</i>')
            await msg2.reply_text('\n'.join([f'<b>{i}</b> : {err[i]}' for i in err]))
        except Exception as e:
            await msg2.edit_text(str(e))
        Config.FOLLOWING = False
    else:
        await msg.reply_text('هنوز عملیاتی فالو قبلی به پایان نرسیده لطفا صبر کنید.')


@app.on_message(filters.user(Config.SUDO) & filters.command('unfollow'))
async def unfollow(_, msg: Message):
    msg2 = await msg.reply_text('لطفا صبر کنید...')
    if not Config.FOLLOWING:
        Config.FOLLOWING = True
        try:
            res = api.user_info(api.authenticated_user_id)
            assert res['user']['following_count'] > 0, 'لیست کاربران فالو شده توسط شما خالی است.'
            await msg2.edit_text('در حال دریافت لیست کاربران فالو شده توسط شما...')
            followings = api.user_following(api.authenticated_user_id, api.generate_uuid())
            n = 0
            for i in followings['users'][:70]:
                result = api.friendships_destroy(i['pk'])
                assert result['status'] == 'ok', result['status']
                n += 1
                await msg2.edit_text('در حال آنفالو کردن....'
                                     f'\nکاربران آنفالو شده : {n}')
                await sleep(3)
            await msg2.reply_text('عملیات آنفالو به پایان رسید')
        except Exception as e:
            await msg2.edit_text(str(e))
        Config.FOLLOWING = False
    else:
        await msg2.reply_text('عملیاتی قبلی هنوز به پایان نرسیده است لطفا صبر کنید')

@app.on_message(filters.user(Config.SUDO) & filters.text & filters.regex(r'^/setfollow (\d+)$'))
async def setfollow(_, msg: Message):
    num = int(msg.matches[0].group(1))
    Config.CN_FOLLOW = num
    await msg.reply_text('محدودیت تنظیم شد.')

app.run()
