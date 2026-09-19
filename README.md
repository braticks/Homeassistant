# Tuščias bakas – Home Assistant

Home Assistant custom integracija Lietuvos degalinių kainoms.

## Duomenų šaltinis

Nuo **0.4.0** integracija naudoja oficialų **Lietuvos energetikos agentūros (LEA)** degalų kainų šaltinį.

LEA duomenyse pateikiama:

- degalinės ir ją valdančios įmonės pavadinimas;
- adresas;
- GPS koordinatės;
- kuro rūšis ir kaina;
- kainos pateikimo laikas;
- oficialus degalinės logotipas, kai jis pateikiamas.

LEA nurodo, kad darbo dienomis degalinės pateikia kainas pagal 10:00 val. būseną, o dalis degalinių informaciją atnaujina ir dažniau. Lojalumo programų nuolaidos į oficialią kainą neįtraukiamos.

## Savaitgalių kainos

Kai LEA konkrečiai degalinei laikinai grąžina kainą be reikšmės, integracija gali naudoti paskutinę anksčiau gautą nenulinę tos pačios degalinės kainą.

Paskutinė žinoma kaina Home Assistant saugoma iki **7 dienų**. Sensoriaus atributas `price_from_cache: true` parodo, kad naudojama paskutinė žinoma kaina.

## Galimybės

- pasirinkti paieškos centro koordinates;
- pasirinkti **1–50 km** spindulį;
- pasirinkti Benziną 95, Dyzeliną arba SND;
- pagal nutylėjimą rodyti tik **Circle K, Neste, Viada ir EMSI**;
- per Configure paslėpti arba parodyti kitus degalinių tinklus;
- nuolaidas kurti per vedlį: **tinklas → savaitės dienos → €/l**;
- pigiausia skelbiama kaina;
- pigiausia kaina po jūsų nuolaidų;
- pigiausia degalinė ir jos adresas;
- artimiausia degalinė ir jos adresas;
- atstumas iki artimiausios degalinės;
- oficialus degalinės logotipas;
- kainos pateikimo laikas atributuose;
- TOP 10 pagal kainą, kainą po nuolaidų ir atstumą.

## Diegimas per HACS

1. HACS → Integrations → ⋮ → **Custom repositories**.
2. Repository: `https://github.com/braticks/Homeassistant`
3. Category: **Integration**.
4. Įdiekite integraciją arba pasirinkite **Redownload**.
5. Perkraukite Home Assistant.
6. Settings → Devices & services → Add integration → **Tuščias bakas**.

## Nustatymai

**Configure** lange yra trys skiltys:

- **Bendri nustatymai** – koordinatės, spindulys, kuro tipas ir atnaujinimo intervalas.
- **Rodomi degalinių tinklai** – pasirenkami tinklai, kurių nenorite matyti.
- **Nuolaidos** – pasirenkamas tinklas, savaitės dienos ir nuolaidos dydis.

## Duomenų priskyrimas

Duomenys: Lietuvos energetikos agentūra (LEA) ir degalines valdančios įmonės.
