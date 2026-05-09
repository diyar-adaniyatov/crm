"""
Human-like conversational responses for the clinic bot.
Provides natural, friendly, and varied responses that feel like a real clinic receptionist.
"""

import random
from typing import List, Dict, Any


class HumanResponses:
    """Collection of human-like response variants for different situations."""

    def __init__(self):
        # Greeting responses — warm, professional, concise
        self.greetings = [
            "Здравствуйте! Подскажу по услугам, ценам и записи.",
            "Добрый день! Чем могу помочь?",
            "Здравствуйте. Помогу с записью или отвечу на вопросы.",
            "Добрый день. Записаться, узнать цену или задать вопрос — пишите.",
            "Доброго времени суток! Чем могу помочь?",
            "Приветствую! На связи, подскажу по услугам и записям.", 
               ]

        # Personalized greetings — {name} placeholder
        self.personalized_greetings = [
            "Здравствуйте, {name}! Чем могу помочь?",
            "Добрый день, {name}! Подскажу по услугам или помогу с записью.",
            "Привет, {name}! На связи. Запись, цена или вопрос?",
            "Доброго времени суток, {name}! Чем могу быть полезен?",
            "Рад вас видеть, {name}! Чем помочь сегодня?",
        ]

        # Returning client greetings
        self.returning_client_greetings = [
            "С возвращением! Чем могу помочь?",
            "Здравствуйте! Снова рады вас видеть. Как могу вам помочь?",
            "С возвращением! Чем могу помочь сегодня?",
            "Рады вас видеть снова! Чем могу быть полезен?",
        ]

        # Service inquiry responses
        self.service_questions = [
            "На какую услугу хотите записаться?",
            "Подскажите, что именно вас интересует?",
            "Какая процедура нужна?",
            "По какой услуге?",
            "Что планируете — напишите, подберём время.",
        ]

        # Name inquiry responses
        self.name_questions = [
            "Как вас записать? Назовите, пожалуйста, имя.",
            "Скажите ваше имя, пожалуйста.",
            "Как к вам обращаться?",
            "Назовите имя — и продолжим.",
            "Уточните имя, пожалуйста.",
            "Как вас зовут? Подскажите имя для записи.",
        ]

        # Phone inquiry responses
        self.phone_questions = [
            "Оставьте, пожалуйста, номер телефона для подтверждения.",
            "Номер телефона — для связи и напоминания.",
            "Какой номер указать?",
            "Пришлите, пожалуйста, номер для подтверждения.",
            "Нужен контактный номер для записи.",
        ]

        # Date/time inquiry responses
        self.datetime_questions = [
            "Когда вам удобно прийти?",
            "Подскажите дату и время для записи.",
            "Когда хотите прийти?",
            "Напишите удобный день и время.",
            "Какое время подойдёт?",
            "Когда вам удобно прийти?",
            "Когда хотите прийти?",
            "Напишите удобный день и время для вашей записи.",
        ]

        # Booking confirmation responses
        self.booking_confirmations = [
            "Готово — запись на {time} оформлена ✅",
            "Записал вас на {time} ✅",
            "Всё готово, ждём вас {time} ✅",
            "Запись подтверждена: {time} ✅",
            "Отлично, вы записаны на {time} ✅",
            "Спасибо за информацию! Записал вас на {time} ✅",
            "Готово, ваша запись на {time} подтверждена ✅",
            "Хорошо, записал вас на {time} ✅",
            "ОК, буду в курсе, что вы придёте в {time} ✅",
        ]

        # Cancellation responses
        self.cancellation_confirmations = [
            "Готово, запись на {time} отменена. Если захотите снова — помогу.",
            "Отменил запись на {time}. Если что, в любой момент запишем заново.",
            "Запись на {time} снял. Будете готовы записаться снова — пишите.",
            "Всё в порядке, визит на {time} отменён. Если нужно — помогу с новой записью.",
            "Убрал запись на {time}. Если понадоблюсь — я здесь.",
            "Ладно, отменил запись на {time}. Если что, подберём новое время.",
            "Хорошо, запись на {time} убрал. Если что обращайтесь, помогу.",
            "Понял, буду в курсе что запись на {time} отменена. Если вдруг снова захотите записаться я здесь.",
        ]

        self.no_active_booking = [
            "Сейчас у вас нет активной записи. Если хотите — могу помочь записаться.",
            "Активной записи пока нет. Если нужно, подберём время.",
            "На данный момент записей нет. Если захотите — помогу оформить.",
            "Сейчас отменять нечего. Если хотите, запишемся заново.",
            "Активной записи не вижу. Если что — я здесь.",
            "Хм, никаких записей нет, помочь оформить",
            "Сейчас у вас пока нечего нету, если хотите я могу помочь записаться", 
            "У вас нет запесей, но я могу разобраться с этим и помочь записаться, если хотите конечно",
        ]

        self.cancellation_errors = [
            "Не смог отменить запись сразу. Попробуйте написать ещё раз.",
            "Что-то пошло не так с отменой. Напишите ещё раз, разберёмся.",
            "Не получилось завершить отмену. Попробуйте снова.",
            "Небольшая заминка с отменой. Давайте повторим.",
            "Пока не удалось отменить запись. Если хотите, продолжим здесь же.",
            "Сейчас не смог отменить запись. Если хотите, попробуем ещё раз сразу здесь.",
            "Не получилось завершить отмену. Напишите ещё раз, и я помогу.",
            "С отменой не вышло с первого раза. Можем сразу повторить.",
            "Пока не удалось отменить запись. Если хотите, продолжим здесь же.",
            "Не смог сейчас подтвердить отмену. Давайте попробуем ещё раз.",
            "Возникли небольшие технические шоколадки, может вам помочь? Просто напишите ещё раз, и я помогу отменить запись.",
        ]

        # Reschedule offer responses
        self.reschedule_offers = [
            "Сейчас запись на {current_time}. Перенести на {new_time}?",
            "Вижу запись на {current_time}. Подойдёт {new_time}?",
            "Могу перенести с {current_time} на {new_time}. Подходит?",
            "Предлагаю {new_time} вместо {current_time}. Подтвердить?",
            "Если удобно, перенесу запись на {new_time}.",
            "Сейчас у вас запись на {current_time}. Хотите перенести её на {new_time}?",
            "Вижу, что вы записаны на {current_time}. Подойдёт ли вам время {new_time}?",
            "Могу предложить перенести вашу запись с {current_time} на {new_time}. Подходит ли вам это время?",
            "Предлагаю перенести вашу запись с {current_time} на {new_time}. Хотите подтвердить перенос?",
            "Если вам удобно, я могу перенести вашу запись на {new_time}. Подтвердите, пожалуйста.",
            "И так ваше время записи {current_tiem}. Может изменим на {new_time}?",
        ]

        # Slot unavailable responses
        self.slot_unavailable = [
            "Это время занято. Могу предложить:\n\n{alternatives}",
            "На это время уже есть запись. Вот свободные:\n\n{alternatives}",
            "Этот слот занят. Посмотрите, пожалуйста:\n\n{alternatives}",
            "Это окно недоступно. Вот ближайшие:\n\n{alternatives}",
            "На это время уже есть запись. Могу предложить:\n\n{alternatives}",
            "Это время уже занято. Могу предложить вам следующие варианты:\n\n{alternatives}",
            "На это время уже есть запись. Вот свободные окна рядом с этим временем:\n\n{alternatives}",
            "Этот слот уже занят. Посмотрите, пожалуйста, другие доступные варианты:\n\n{alternatives}",
            "Это окно недоступно. Вот ближайшие свободные слоты:\n\n{alternatives}",
            "На это время уже есть запись. Могу предложить следующие альтернативные варианты:\n\n{alternatives}",
            "Извините, но к сожалению это время занято. Могу вас записать на \n\n{alternatives}",

        ]

        # No alternatives available
        self.no_alternatives = [
            "Пока ближайших свободных окон нет.",
            "На ближайшие дни всё занято.",
            "Free slots не вижу прямо сейчас.",
            "Ближайших мест нет. Попробуйте другую дату.",
            "Пока не вижу доступных вариантов рядом с этим временем.",
            "Пока ближайших свободных окон не вижу.",
            "На ближайшее время всё занято.",
            "Других свободных окон пока нет.",
            "Свободных мест на ближайшие дни сейчас нет.",
            "Пока не вижу доступных вариантов рядом с этим временем.",
            "Приносим извинения — на ближайшее время всё занято. Попробуйте другую дату или время.",
            "Извините пожалуста, но на ближайшее время всё занято. Выберете другое время.",
        ]

        # Missing information responses
        self.missing_info = [
            "Нужно уточнить: {fields}.",
            "Подскажите, пожалуйста: {fields}.",
            "Мне ещё нужны {fields}.",
            "Уточните {fields}, пожалуйста.",
            "Не хватает данных: {fields}.",
            "Для продолжения нужно уточнить: {fields}.",
            "Пожалуйста, уточните следующие данные: {fields}.",
            "Мне ещё нужны следующие данные: {fields}.",
            "Уточните, пожалуйста, следующие поля: {fields}.",
            "Нет хватает данных для продолжения: {fields}.",
        ]

        # Price inquiry responses
        self.price_responses = [
            "{service} — {price} тг, примерно {duration} минут.",
            "По услуге {service}: {price} тг, около {duration} минут.",
            "Стоимость {service} — {price} тг. По времени ~{duration} мин.",
            "{service} стоит {price} тг, приём занимает около {duration} минут.",
            "По цене: {service} — {price} тг, длительность примерно {duration} минут.",
            "{service} стоит {price} тг, и занимает примерно {duration} минут.",
            "Стоимость услуги {service} составляет {price} тг, а по времени это примерно {duration} минут.",
            "По услуге {service}, цена составляет {price} тг, а длительность приёма — около {duration} минут.",
            "Цена на {service} — {price} тг, и обычно приём занимает около {duration} минут.",
            "Стоимость для услуги {service} — {price} тг, а по времени это примерно {duration} минут.",
        ]

        # Price not available responses
        self.price_not_available = [
            "Стоимость {service} лучше уточнить у администратора.",
            "По {service} цена зависит от деталей, лучше уточнить при обращении.",
            "По {service} стоимость рассчитывается индивидуально.",
            "Точную цену на {service} подскажет администратор.",
            "По {service} цена может отличаться, лучше уточнить отдельно.",
            "Стоимость услуги {service} может зависеть от разных факторов, лучше уточнить у администратора.",
            "По услуге {service} точную цену лучше узнать при обращении, так как она может варьироваться.",
            "Цена на {service} может быть разной в зависимости от деталей, рекомендую уточнить у администратора.",
            "Точную стоимость для услуги {service} вам подскажет администратор, так как она может отличаться в разных случаях.",
            "По {service} стоимость может отличаться, поэтому лучше уточнить её при обращении к администратору.",
        ]

        self.price_overview = [
            "По ценам сейчас так:\n\n{items}",
            "Вот кратко по стоимости:\n\n{items}",
            "По прайсу:\n\n{items}",
            "Могу ориентировать по ценам:\n\n{items}",
            "Вот краткий обзор цен:\n\n{items}",
            "По ценам сейчас примерно так:\n\n{items}",
            "Вот кратко по стоимости услуг:\n\n{items}",
            "По прайсу на текущий момент:\n\n{items}",
            "Я могу подсказать ориентировочные цены:\n\n{items}",
        ]

        self.info_missing = [
            "По {topic} пока нет точной информации в системе. Если важно — помогу уточнить у администратора.",
            "По {topic} данные пока не заполнены. Если нужно, передам вопрос.",
            "Точных данных по {topic} прямо сейчас нет. Могу помочь с другим вопросом.",
            "По {topic} пока нет подсказки в системе. Уточните у администратора.",
            "По {topic} точной информации сейчас нет. Если нужно, помогу уточнить это отдельно.",
            "По {topic} сейчас не вижу точной информации в системе. Если захотите, позже уточню у администратора.",
            "Пока не подгрузились точные данные по {topic}. Если это важно, помогу уточнить.",
            "По {topic} точной информации сейчас нет. При необходимости передам вопрос администратору.",
            "Сейчас не вижу в карточке клиники данных по {topic}. Если нужно, помогу уточнить это отдельно.",
            "По {topic} пока нет точной подсказки в системе. Если захотите, вернусь с уточнением.",
        ]

        # Services list responses
        self.services_list = [
            "Вот что у нас есть:\n\n{services}",
            "Доступные услуги:\n\n{services}",
            "Я могу предложить вам:\n\n{services}",
            "Сейчас доступны:\n\n{services}",
            "По услугам вот что есть:\n\n{services}",
            "Вот список наших услуг:\n\n{services}",
            "Доступные услуги в нашей клинике:\n\n{services}",
            "Могу предложить вам следующие услуги:\n\n{services}",
            "Сейчас в нашем прайсе доступны следующие услуги:\n\n{services}",
            "Вот что мы можем предложить по услугам:\n\n{services}",
        ]

        # FAQ responses
        self.faq_responses = [
            "{answer}",
            "Подсказываю: {answer}",
            "По этому вопросу: {answer}",
            "Да, конечно — {answer}",
            "Вот информация по этому вопросу: {answer}",
            "Подсказываю по вашему вопросу: {answer}",
            "По этому вопросу могу сказать следующее: {answer}",
            "Да, конечно — вот ответ на ваш вопрос: {answer}",
            "Вот информация по этому вопросу: {answer}",
            "Подсказываю по вашему вопросу: {answer}",
            "По этому вопросу могу сказать следующее: {answer}",
            "Да, конечно — вот ответ на ваш вопрос: {answer}",
        ]

        # Forward to admin responses
        self.forward_to_admin = [
            "Передал ваш вопрос администратору.",
            "Хорошо, передам это администратору.",
            "Сообщение передано, с вами свяжутся.",
            "Принял, передаю администратору.",
            "Администратор увидит ваш вопрос в ближайшее время.",
            "Хорошо, я передам ваш вопрос администратору, он свяжется с вами в ближайшее время.",
            "Понял, сейчас передам ваш вопрос человеку, он свяжется с вами в ближайшее время.",
            "Сообщение отправлю администратору, он свяжется с вами в ближайшее время.",
            "Хорошо, подключим администратора, он свяжется с вами в ближайшее время.",
            "Передаю ваш вопрос администратору, он увидит его в ближайшее время и свяжется с вами.",
        ]

        # Operator request responses
        self.operator_requests = [
            "Хорошо, передам вопрос администратору. Он ответит в ближайшее время.",
            "Понял, сейчас передам ваш вопрос человеку.",
            "Передаю вашему администратору — он скоро свяжется.",
            "Хорошо, подключим администратора.",
            "Передаю ваш вопрос администратору.",
            "Хорошо, я передам ваш вопрос администратору, он свяжется с вами в ближайшее время.",
            "Понял, сейчас передам ваш вопрос человеку, он свяжется с вами в ближайшее время.",
            "Сообщение отправлю администратору, он свяжется с вами в ближайшее время.",
            "Хорошо, подключим администратора, он свяжется с вами в ближайшее время.",
            "Передаю ваш вопрос администратору, он увидит его в ближайшее время и свяжется с вами.",
        ]

        # Generic clarification when intent is unclear
        self.error_responses = [
            "Не до конца понял. Запись, цена или вопрос?",
            "Подскажите, пожалуйста, что нужно.",
            "Уточните в двух словах, чем помочь.",
            "Что хотите сделать: записаться, перенести или задать вопрос?",
            "Сориентируйте меня: запись или вопрос?",
            "Понял не всё. Что хотите сделать?",
            "Сориентируйте меня, пожалуйста: запись или вопрос?",
            "Извините, я не совсем понял. Вы хотите записаться, узнать цену или задать вопрос?",
            "Пожалуйста, уточните, чем я могу помочь: запись, перенос или вопрос?",
            "Извините, я не совсем понял ваш запрос. Вы хотите записаться на приём, узнать стоимость услуги или задать другой вопрос?",
        ]

        self.booking_errors = [
            "Не получилось завершить запись сразу. Напишите ещё раз — подхвачу.",
            "Что-то пошло не так. Попробуйте снова.",
            "Давайте ещё раз — я готов.",
            "Небольшая заминка. Напишите ещё раз, я помогу.",
            "Пока не удалось завершить запись. Если хотите, продолжим здесь же.",
            "Сейчас не смог завершить запись. Если хотите, попробуем ещё раз сразу здесь.",
            "Не получилось завершить запись. Напишите ещё раз, и я помогу.",
            "С записью не вышло с первого раза. Можем сразу повторить.",
            "Пока не удалось завершить запись. Если хотите, продолжим здесь же.",
        ]

        self.clarifying_questions = [
            "Завись, стоимость или вопрос — что интересует?",
            "Что именно нужно: записаться, узнать цену или задать вопрос?",
            "Чем помочь: запись, цена или информация по услугам?",
            "Сориентируйте меня: запись или вопрос?",
            "С чего начнём: запись, перенос или другой вопрос?",
            "Понял не всё. Что хотите сделать?",
        ]

        self.invalid_datetime = [
            "Не понял дату и время.",
            "Укажите дату и время чуть точнее — например: 7 апреля в 15:30.",
            "Пока не разобрал время. Подойдёт: сегодня в 16:55.",
            "Нужно уточнить время визита. Например: послезавтра в 14:05.",
            "Не совсем понял дату и время. Например: завтра в 17:16.",
            "Пока не разобрал дату и время. Подойдёт: сегодня в 18:30.",
            "Нужно уточнить дату и время визита.",
            "Например: послезавтра в 14:00.",
            "Не совсем понял дату и время. Например: завтра в 17:10.",
            "Пока не разобрал дату и время. Подойдёт: сегодня в 11:30.",
            "Нужно уточнить дату и время визита. Например: послезавтра в 12:00.",
        ]

        self.past_datetime = [
            "Это время уже прошло. Давайте выберем другое.",
            "На прошедшее время записать не получится — подскажите будущий слот.",
            "Этот момент уже позади. Напишите другое время.",
            "Нужно выбрать время позже текущего.",
            "Это время уже прошло. Давайте выберем другое.",
            "На прошедшее время записать не получится — подскажите будущий слот.",
            "Этот момент уже позади. Напишите другое время.",
            "Нужно выбрать время позже текущего.",
        ]

        self.outside_working_hours = [
            "Клиника работает с {start} до {end}. Выберите время в этом диапазоне.",
            "В это время клиника не работает. Мы принимаем с {start} до {end}.",
            "Этот слот выходит за график. Доступное время: с {start} до {end}.",
            "Выберите, пожалуйста, время с {start} до {end}.",
            "Клиника работает с {start} до {end}. Пожалуйста, выберите время в этом диапазоне.",
            "В это время клиника не работает. Мы принимаем с {start} до {end}. Пожалуйста, выберите время в этом диапазоне.",
            "Этот слот выходит за график. Доступное время: с {start} до {end}.",
            "Выберите, пожалуйста, время с {start} до {end}.",
            "Клиника работает с {start} до {end}. Пожалуйста, выберите время в этом диапазоне.",
        ]

        # Reset responses
        self.reset_success = [
            "Готово. Чем помочь дальше?",
            "Обновил. Что вас интересует?",
            "Продолжим. Чем помочь?",
            "Готово, на связи.",
            "Обновил. Чем помочь дальше?",
            "Продолжим. Чем помочь?",
            "Готово, на связи.",
            "Обновил. Что вас интересует?",
            "Продолжим. Чем помочь?",
            "Готово, на связи.",
            "Готово. Чем помочь дальше?",
            "Обновил. Что вас интересует?",
            "Продолжим. Чем помочь?",
        ]

        self.reset_error = [
            "Просто повторите запрос ещё раз, и продолжим.",
            "Напишите запрос снова — подхвачу отсюда.",
            "Можно просто написать снова — я готов.",
            "Давайте повторим запрос — я подхвачу.",
            "Пока не получилось, просто повторите запрос ещё раз, и продолжим.",
            "Напишите запрос снова — подхвачу отсюда.",
            "Можно просто написать снова — я готов.",
            "Давайте повторим запрос — я подхвачу.",
            "Пока не получилось, просто повторите запрос ещё раз, и продолжим.",
            "Напишите запрос снова — подхвачу отсюда.",
            "Можно просто написать снова — я готов.",
        ]

        # No services available
        self.no_services = [
            "Список услуг пока не заполнен.",
            "Услуги пока не добавлены в систему.",
            "Сейчас список услуг пуст — уточните у администратора.",
            "Пока не вижу доступных услуг. Уточните у администратора.",
            "Список услуг пока не заполнен. Если нужно, помогу уточнить у администратора.",
            "Услуги пока не добавлены в систему. Если нужно, помогу уточнить у администратора.",
            "Сейчас список услуг пуст — уточните у администратора, если это важно.",
            "Пока не вижу доступных услуг. Если нужно, помогу уточнить у администратора.",
            "Список услуг пока не заполнен. Если нужно, помогу уточнить у администратора.",
            "Услуги пока не добавлены в систему. Если нужно, помогу уточнить у администратора.",
        ]

        self.no_bookings = [
            "Активных записей сейчас нет.",
            "Пока записей нет.",
            "Сейчас нет активной записи.",
            "Пока не вижу активных записей.",
            "Активных записей сейчас нет. Если хотите, могу помочь записаться.",
            "Пока записей нет. Если нужно, подберём время для новой записи.",
            "Сейчас нет активной записи. Если хотите, могу помочь записаться.",
            "Пока не вижу активных записей. Если нужно, подберём время для новой записи.",
            "Активных записей сейчас нет. Если хотите, могу помочь записаться.",
            "Пока записей нет. Если нужно, подберём время для новой записи.",
            "Сейчас нет активной записи. Если хотите, могу помочь записаться.",
            "Пока не вижу активных записей. Если нужно, подберём время для новой записи.",
        ]

        # Reschedule confirmation responses
        self.reschedule_confirmations = [
            "Готово, перенёс запись на {time} ✅",
            "Запись перенесена на {time} ✅",
            "Теперь запись стоит на {time} ✅",
            "Перенёс на {time} ✅",
            "Отлично, ваша запись теперь на {time} ✅",
            "Готово, ваша запись теперь на {time} ✅",
            "Хорошо, перенёс вашу запись на {time} ✅",
            "ОК, буду в курсе, что вы придёте в {time} ✅",
            "Всё готово, ваша запись перенесена на {time} ✅",
        ]

        # "Спасибо" acknowledgement
        self.thanks_responses = [
            "Пожалуйста! Если что-то изменится, напишите — помогу.",
            "Всегда рады! Если нужно — я здесь.",
            "Не за что. Ждём вас!",
            "Пожалуйста. Если что — пишите.",
        ]

        # When user already has a booking and tries to create another
        self.booking_already_exists = [
            "У вас уже есть запись на {time} ({service}). Хотите изменить время — напишите новое, хотите отменить — напишите «отменить».",
            "Запись уже оформлена: {time} ({service}). Если нужно изменить — скажите новое время или «перенести».",
            "Уже записаны на {time} ({service}). Перенести или отменить? Просто напишите.",
            "У вас уже есть запись на {time} ({service}). Если хотите изменить время — напишите новое, если нужно отменить — напишите «отменить».",
        ]

    def get_random_response(self, response_type: str, **kwargs) -> str:
        """Get a random response variant for the given type."""
        responses = getattr(self, response_type, [])
        if not responses:
            return "Подскажите, пожалуйста, что вас интересует."

        response = random.choice(responses)

        # Format with provided kwargs
        try:
            return response.format(**kwargs)
        except (KeyError, ValueError):
            return response


# Global instance for easy access
human_responses = HumanResponses()


def get_greeting() -> str:
    return human_responses.get_random_response('greetings')


def get_personalized_greeting(name: str) -> str:
    """Get a personalized greeting using the user's first name."""
    first = (name or "").strip().split()[0] if name else ""
    if first:
        return human_responses.get_random_response('personalized_greetings', name=first)
    return get_greeting()


def get_returning_client_greeting() -> str:
    return human_responses.get_random_response('returning_client_greetings')


def get_service_question() -> str:
    return human_responses.get_random_response('service_questions')


def get_name_question() -> str:
    return human_responses.get_random_response('name_questions')


def get_phone_question() -> str:
    return human_responses.get_random_response('phone_questions')


def get_datetime_question() -> str:
    return human_responses.get_random_response('datetime_questions')


def get_booking_confirmation(time: str, service: str = "") -> str:
    return human_responses.get_random_response('booking_confirmations', time=time, service=service)


def get_cancellation_confirmation(time: str, service: str = "") -> str:
    return human_responses.get_random_response('cancellation_confirmations', time=time, service=service)


def get_no_active_booking_response() -> str:
    return human_responses.get_random_response('no_active_booking')


def get_cancellation_error_response() -> str:
    return human_responses.get_random_response('cancellation_errors')


def get_reschedule_offer(current_time: str, new_time: str) -> str:
    return human_responses.get_random_response('reschedule_offers', current_time=current_time, new_time=new_time)


def get_slot_unavailable_message(alternatives: str) -> str:
    return human_responses.get_random_response('slot_unavailable', alternatives=alternatives)


def get_no_alternatives_message() -> str:
    return human_responses.get_random_response('no_alternatives')


def get_missing_info_message(fields: str) -> str:
    return human_responses.get_random_response('missing_info', fields=fields)


def get_price_response(service: str, price: str, duration: str) -> str:
    pretty_price = str(price)
    if isinstance(price, (int, float)):
        pretty_price = f"{int(price):,}".replace(",", " ")
    return human_responses.get_random_response('price_responses', service=service, price=pretty_price, duration=duration)


def get_price_not_available_response(service: str) -> str:
    return human_responses.get_random_response('price_not_available', service=service)


def get_services_list_response(services: str) -> str:
    return human_responses.get_random_response('services_list', services=services)


def get_price_overview_response(items: str) -> str:
    return human_responses.get_random_response('price_overview', items=items)


def get_info_missing_response(topic: str) -> str:
    return human_responses.get_random_response('info_missing', topic=topic)


def get_faq_response(answer: str) -> str:
    return human_responses.get_random_response('faq_responses', answer=answer)


def get_forward_to_admin_response() -> str:
    return human_responses.get_random_response('forward_to_admin')


def get_operator_request_response() -> str:
    return human_responses.get_random_response('operator_requests')


def get_error_response() -> str:
    return human_responses.get_random_response('error_responses')


def get_clarifying_question() -> str:
    return human_responses.get_random_response('clarifying_questions')


def get_booking_error_response() -> str:
    return human_responses.get_random_response('booking_errors')


def get_invalid_datetime_response() -> str:
    return human_responses.get_random_response('invalid_datetime')


def get_past_datetime_response() -> str:
    return human_responses.get_random_response('past_datetime')


def get_outside_working_hours_response(start: str = "10:00", end: str = "19:00") -> str:
    return human_responses.get_random_response('outside_working_hours', start=start, end=end)


def get_reset_success_response() -> str:
    return human_responses.get_random_response('reset_success')


def get_reset_error_response() -> str:
    return human_responses.get_random_response('reset_error')


def get_no_services_response() -> str:
    return human_responses.get_random_response('no_services')


def get_no_bookings_response() -> str:
    return human_responses.get_random_response('no_bookings')


def get_reschedule_confirmation(time: str) -> str:
    return human_responses.get_random_response('reschedule_confirmations', time=time)


def get_thanks_response() -> str:
    return add_reply_icon(human_responses.get_random_response('thanks_responses'), "🙏")


def get_booking_already_exists_response(time: str, service: str) -> str:
    return add_reply_icon(human_responses.get_random_response('booking_already_exists', time=time, service=service), "ℹ️")

# Global instance for easy access
human_responses = HumanResponses()


def add_reply_icon(text: str, icon: str) -> str:
    """Prefix a bot reply with one small visual cue when it is useful."""
    value = (text or "").strip()
    if not value or value.startswith(icon):
        return value
    return f"{icon} {value}"


def get_greeting() -> str:
    """Get a random greeting response."""
    return add_reply_icon(human_responses.get_random_response('greetings'), "👋")


def get_service_question() -> str:
    """Get a random service question."""
    return add_reply_icon(human_responses.get_random_response('service_questions'), "🦷")


def get_name_question() -> str:
    """Get a random name question."""
    return add_reply_icon(human_responses.get_random_response('name_questions'), "👤")


def get_phone_question() -> str:
    """Get a random phone question."""
    return add_reply_icon(human_responses.get_random_response('phone_questions'), "📞")


def get_datetime_question() -> str:
    """Get a random datetime question."""
    return add_reply_icon(human_responses.get_random_response('datetime_questions'), "🗓️")


def get_booking_confirmation(time: str, service: str = "") -> str:
    """Get a random booking confirmation."""
    return add_reply_icon(human_responses.get_random_response('booking_confirmations', time=time, service=service), "✅")


def get_cancellation_confirmation(time: str, service: str = "") -> str:
    """Get a random cancellation confirmation."""
    return add_reply_icon(human_responses.get_random_response('cancellation_confirmations', time=time, service=service), "✅")


def get_no_active_booking_response() -> str:
    """Get a friendly response when there is no active booking to cancel."""
    return add_reply_icon(human_responses.get_random_response('no_active_booking'), "ℹ️")


def get_cancellation_error_response() -> str:
    """Get a friendly response when automatic cancellation fails."""
    return add_reply_icon(human_responses.get_random_response('cancellation_errors'), "⚠️")


def get_reschedule_offer(current_time: str, new_time: str) -> str:
    """Get a random reschedule offer."""
    return add_reply_icon(human_responses.get_random_response('reschedule_offers', current_time=current_time, new_time=new_time), "🗓️")


def get_slot_unavailable_message(alternatives: str) -> str:
    """Get a random slot unavailable message."""
    return add_reply_icon(human_responses.get_random_response('slot_unavailable', alternatives=alternatives), "⏰")


def get_no_alternatives_message() -> str:
    """Get a random no alternatives message."""
    return add_reply_icon(human_responses.get_random_response('no_alternatives'), "⏰")


def get_missing_info_message(fields: str) -> str:
    """Get a random missing info message."""
    return add_reply_icon(human_responses.get_random_response('missing_info', fields=fields), "ℹ️")


def get_price_response(service: str, price: str, duration: str) -> str:
    """Get a random price response."""
    pretty_price = str(price)
    if isinstance(price, (int, float)):
        pretty_price = f"{int(price):,}".replace(",", " ")
    return add_reply_icon(human_responses.get_random_response('price_responses', service=service, price=pretty_price, duration=duration), "💳")


def get_price_not_available_response(service: str) -> str:
    """Get a random price not available response."""
    return add_reply_icon(human_responses.get_random_response('price_not_available', service=service), "ℹ️")


def get_services_list_response(services: str) -> str:
    """Get a random services list response."""
    return add_reply_icon(human_responses.get_random_response('services_list', services=services), "🦷")


def get_price_overview_response(items: str) -> str:
    """Get a short overview response for general price questions."""
    return add_reply_icon(human_responses.get_random_response('price_overview', items=items), "💳")


def get_info_missing_response(topic: str) -> str:
    """Get a graceful response when clinic info is missing."""
    return add_reply_icon(human_responses.get_random_response('info_missing', topic=topic), "ℹ️")


def get_faq_response(answer: str) -> str:
    """Get a random FAQ response."""
    return add_reply_icon(human_responses.get_random_response('faq_responses', answer=answer), "ℹ️")


def get_forward_to_admin_response() -> str:
    """Get a random forward to admin response."""
    return add_reply_icon(human_responses.get_random_response('forward_to_admin'), "👩‍💼")


def get_operator_request_response() -> str:
    """Get a random operator request response."""
    return add_reply_icon(human_responses.get_random_response('operator_requests'), "👩‍💼")


def get_error_response() -> str:
    """Get a random error response."""
    return add_reply_icon(human_responses.get_random_response('error_responses'), "⚠️")


def get_clarifying_question() -> str:
    """Get a short clarifying question for unclear free-form messages."""
    return add_reply_icon(human_responses.get_random_response('clarifying_questions'), "✨")


def get_booking_error_response() -> str:
    """Get a random booking lifecycle error response."""
    return add_reply_icon(human_responses.get_random_response('booking_errors'), "⚠️")


def get_invalid_datetime_response() -> str:
    """Get a friendly invalid date/time response."""
    return add_reply_icon(human_responses.get_random_response('invalid_datetime'), "🗓️")


def get_past_datetime_response() -> str:
    """Get a friendly response for past times."""
    return add_reply_icon(human_responses.get_random_response('past_datetime'), "⏰")


def get_outside_working_hours_response(start: str = "10:00", end: str = "19:00") -> str:
    """Get a working-hours guidance response."""
    return add_reply_icon(human_responses.get_random_response('outside_working_hours', start=start, end=end), "⏰")


def get_reset_success_response() -> str:
    """Get a random reset success response."""
    return add_reply_icon(human_responses.get_random_response('reset_success'), "✅")


def get_reset_error_response() -> str:
    """Get a random reset error response."""
    return add_reply_icon(human_responses.get_random_response('reset_error'), "⚠️")


def get_no_services_response() -> str:
    """Get a random no services response."""
    return add_reply_icon(human_responses.get_random_response('no_services'), "ℹ️")


def get_no_bookings_response() -> str:
    """Get a random no bookings response."""
    return add_reply_icon(human_responses.get_random_response('no_bookings'), "ℹ️")


def get_reschedule_confirmation(time: str) -> str:
    """Get a random reschedule confirmation."""
    return add_reply_icon(human_responses.get_random_response('reschedule_confirmations', time=time), "✅")
