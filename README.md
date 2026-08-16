# Дипломен проект: двуканално измерване на напрежение

Това е първият работещ прототип на измервателната система. Два потенциометъра
задават две независими напрежения, Arduino Uno ги измерва през `A0` и `A1`, а
Python ги получава и визуализира в реално време.

```text
POT 1 -> A0 --\
               Arduino Uno -> Serial/RFC2217 -> Python -> графика/CSV
POT 2 -> A1 --/
```

Симулацията започва приблизително с `U1 = 1.43 V` и `U2 = 1.95 V`. Общите
`5V` и `GND` са разклонени към двата потенциометъра в `diagram.json`.

## Необходими програми

- [Visual Studio Code](https://code.visualstudio.com/)
- разширението **PlatformIO IDE**
- разширението **Wokwi Simulator**
- Python 3.10 или по-нова версия

VS Code ще предложи двете разширения автоматично при отваряне на папката.
При първото използване на Wokwi изпълни `F1` -> `Wokwi: Request a New License`
и следвай показаните стъпки.

## 1. Подготовка на Python

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Графиката може да се провери веднага, без микроконтролер:

```bash
python read_voltage.py --demo
```

Затвори прозореца на графиката или натисни `Ctrl+C`, за да спреш програмата.

## 2. Компилиране и стартиране на Wokwi

1. Отвори цялата папка в VS Code.
2. Изчакай PlatformIO да подготви средата.
3. Натисни **PlatformIO: Build** (иконата с отметка в долната лента).
4. Отвори `diagram.json`.
5. Натисни зеления бутон за стартиране или изпълни
   `F1` -> `Wokwi: Start Simulator`.
6. Остави раздела на симулатора видим, за да не бъде поставена симулацията на
   пауза.

`wokwi.toml` отваря виртуалния сериен порт като RFC2217 сървър на
`localhost:4000`.

## 3. Получаване на реалните данни в Python

Докато Wokwi симулацията работи, отвори втори терминал, активирай Python
средата и изпълни:

```bash
python read_voltage.py
```

Завъртането на `POT 1` трябва да променя само зелената линия `U1`, а `POT 2` —
само синята линия `U2`.

Само текстови стойности в терминала:

```bash
python read_voltage.py --no-plot
```

Едновременно показване и запис в CSV:

```bash
python read_voltage.py --csv measurements.csv
```

За истинско Arduino вместо Wokwi подай името на серийния порт:

```bash
# Linux пример
python read_voltage.py --url /dev/ttyACM0

# Windows пример
python read_voltage.py --url COM3
```

## Формат на данните

Arduino изпраща по един CSV ред на всеки 100 ms:

```text
1.430,1.950
1.435,1.950
```

Python проверява всеки ред и пропуска повредени или невалидни данни. Кодът
усреднява по осем ADC преобразувания на канал и отхвърля първото измерване след
превключване на аналоговия мултиплексор.

## Проверка на Python кода

Тестовете не изискват външни библиотеки:

```bash
python -m unittest discover -s tests -v
```

## Следващ етап: National Instruments

При окончателната система източникът ще се смени:

```text
сега:   Arduino -> Serial -> pyserial -> Python
после:  NI DAQ  -> NI-DAQmx -> nidaqmx -> Python
```

Парсването, графиката и CSV записът могат да останат като основа. За реалната
NI реализация са нужни точният модел на устройството, имената и типът на
каналите, входният диапазон и желаната честота на дискретизация.

