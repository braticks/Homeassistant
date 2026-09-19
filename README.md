# Tuščias bakas – Home Assistant

Home Assistant custom integracija Lietuvos degalinių kainoms.

## Duomenų šaltinis

Nuo **0.3.0** kuro kainos imamos iš **Kurohudas.lt** miesto puslapių. Kurohudas nurodo LEA, degalinių tinklų skelbiamas kainas per duomenų partnerį ir savo bendruomenę kaip duomenų šaltinius.

Tikslios degalinių koordinatės paimamos iš Kurohudas degalinės navigacijos nuorodos ir išsaugomos Home Assistant cache. Todėl jų nereikia parsisiųsti kiekvieno kainų atnaujinimo metu.

Kurohudas miesto puslapis pateikia degalines iki **12 km nuo pasirinkto miesto**, todėl integracijos radiusas yra 1–12 km.

## Galimybės

- pasirinkti miestą, pvz. **Kaunas**;
- pasirinkti paieškos centro koordinates;
- pasirinkti **1–12 km** spindulį;
- pasirinkti kurą: Benzinas 95, Dyzelinas arba SND;
- pagal nutylėjimą rodyti tik **Circle K, Neste, Viada ir EMSI**;
- per Configure paslėpti / parodyti kitus tinklus;
- nuolaidas kurti per vedlį: **tinklas → savaitės dienos → €/l**;
- pigiausia skelbiama kaina;
- pigiausia kaina po nuolaidų;
- pigiausia degalinė ir jos adresas;
- artimiausia degalinė ir jos adresas;
- atstumas iki artimiausios degalinės;
- Kurohudas kainos data ir konkrečios degalinės atnaujinimo žyma atributuose;
- TOP 10 pagal kainą, kainą po nuolaidų ir atstumą.

## Diegimas per HACS

1. HACS → Integrations → ⋮ → **Custom repositories**.
2. Repository: `https://github.com/braticks/Homeassistant`
3. Category: **Integration**.
4. Įdiek arba pasirink **Redownload → Code**.
5. Perkrauk Home Assistant.
6. Settings → Devices & services → Add integration → **Tuščias bakas**.

## Nustatymai

**Configure** lange yra trys skiltys:

- **Bendri nustatymai** – miestas, koordinatės, spindulys, kuro tipas, atnaujinimo intervalas.
- **Rodomi degalinių tinklai** – pažymimi tinklai, kurių nenorite matyti.
- **Nuolaidos** – nuolaida kuriama pasirenkant tinklą, dienas ir dydį.

## Pastaba

Kurohudas neturi viešai dokumentuoto API, todėl integracija skaito viešai pateikiamą miesto kainų lentelę ir degalinių navigacijos nuorodas. Jei Kurohudas pakeis puslapio HTML struktūrą, parserį gali reikėti atnaujinti.
