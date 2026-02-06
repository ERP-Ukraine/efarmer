<?xml version="1.0" encoding="UTF-8" ?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:tns="http://crd.gov.pl/wzor/2025/06/25/13775/"
                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                version="1.0">

    <xsl:output method="html"
                encoding="UTF-8"
                indent="yes"
                version="5.0"
                doctype-public="-//W3C//DTD HTML 4.01//EN"
                doctype-system="http://www.w3.org/TR/html4/strict.dtd"/>

    <xsl:param name="schema-krajow" select="'KodyKrajow_v10-0E.xsd'"/>

    <xsl:template match="tns:Faktura">
        <xsl:call-template name="PrzyczynaKorekty"/>
        <xsl:call-template name="SprzedawcaNabywca"/>
        <xsl:call-template name="Szczegoly"/>
        <xsl:call-template name="FakturaWiersze"/>
        <xsl:call-template name="PodliczenieVAT"/>
        <xsl:call-template name="Adnotacje"/>
        <xsl:call-template name="Platnosc"/>
        <xsl:call-template name="WarunkiTransakcji"/>
        <xsl:call-template name="WZ"/>
    </xsl:template>

	<xsl:template name="PrzyczynaKorekty">
		<xsl:for-each select="tns:Fa">
			<xsl:if test="tns:PrzyczynaKorekty|tns:TypKorekty|tns:DaneFaKorygowanej">
            <div class="row">
                <xsl:if test="tns:PrzyczynaKorekty|tns:TypKorekty">
                    <div class="col-6">
                        <h6 class="fw-bold">Dane faktury korygowanej</h6>
                        <xsl:if test="tns:PrzyczynaKorekty">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Przyczyna korekty dla faktur korygujących: </xsl:text>
                                </strong>
                                <xsl:value-of select="tns:PrzyczynaKorekty"/>
                            </p>
                        </xsl:if>

                        <xsl:if test="tns:TypKorekty">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Typ skutku korekty: </xsl:text>
                                </strong>
                                <xsl:choose>
                                    <xsl:when test="tns:TypKorekty = '1'">
                                        <xsl:text>Korekta skutkująca w dacie ujęcia faktury pierwotnej</xsl:text>
                                    </xsl:when>
                                    <xsl:when test="tns:TypKorekty = '2'">
                                        <xsl:text>Korekta skutkująca w dacie wystawienia faktury korygującej</xsl:text>
                                    </xsl:when>
                                    <xsl:when test="tns:TypKorekty = '3'">
                                        <xsl:text>
                                            Korekta skutkująca w dacie innej, w tym gdy dla różnych pozycji faktury
                                            korygującej daty te są różne
                                        </xsl:text>
                                    </xsl:when>
                                </xsl:choose>
                            </p>
                        </xsl:if>
                    </div>
                </xsl:if>

                <xsl:if test="tns:DaneFaKorygowanej">
                    <div class="col-6">
                        <h6 class="fw-bold">Dane identyfikacyjne faktury korygowanej</h6>
                        <xsl:for-each select="tns:DaneFaKorygowanej">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Data wystawienia faktury, której dotyczy faktura korygująca: </xsl:text>
                                </strong>
                                <xsl:value-of select="tns:DataWystFaKorygowanej"/>
                            </p>

                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Numer faktury korygowanej: </xsl:text>
                                </strong>
                                <xsl:value-of select="tns:NrFaKorygowanej"/>
                            </p>

                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Numer KSeF faktury korygowanej: </xsl:text>
                                </strong>
                                <xsl:value-of select="tns:NrKSeFFaKorygowanej"/>
                            </p>
                        </xsl:for-each>
                    </div>
                </xsl:if>
            </div>
            <hr/>
            </xsl:if>
		</xsl:for-each>
	</xsl:template>

    <xsl:template name="Szczegoly">
        <h6 class="fw-bold">Szczegóły</h6>
        <div class="row">
            <div class="col-6">
                <strong>Data wystawienia, z zastrzeżeniem art. 106 na ust. 1 ustawy: </strong>
                <xsl:value-of select="tns:Fa/tns:P_1"/>
            </div>

            <xsl:if test="tns:Fa/tns:P_1M">
                <div class="col-6">
                    <strong>Miejsce wystawienia: </strong>
                    <xsl:value-of select="tns:Fa/tns:P_1M"/>
                </div>
            </xsl:if>

            <xsl:if test="tns:Fa/tns:P_6|tns:Fa/tns:OkresFa">
                <div class="col-6">
                    <strong>Data dokonania lub zakończenia dostawy towarów lub wykonania usługi: </strong>
                    <xsl:choose>
                        <xsl:when test="tns:Fa/tns:P_6">
                            <xsl:value-of select="tns:Fa/tns:P_6"/>
                        </xsl:when>

                        <xsl:when test="tns:Fa/tns:OkresFa">
                            <strong>od </strong>
                            <xsl:value-of select="tns:Fa/tns:OkresFa/tns:P_6_Od"/>
                            <strong> do </strong>
                            <xsl:value-of select="tns:Fa/tns:OkresFa/tns:P_6_Do"/>
                        </xsl:when>
                    </xsl:choose>
                </div>
            </xsl:if>

            <xsl:if test="tns:Fa/tns:KursWalutyZ">
                <div class="col-6">
                    <strong>Kurs waluty: </strong>
                    <xsl:value-of select="tns:Fa/tns:KursWalutyZ"/>
                </div>
            </xsl:if>
        </div>
        <hr/>
    </xsl:template>

    <xsl:template name="SprzedawcaNabywca">
        <div class="row">
            <div class="col-6">
                <h6 class="fw-bold">Sprzedawca</h6>
                <xsl:if test="tns:Podmiot1/tns:NrEORI">
                    <p class="mb-0">
                        <strong>
                            <xsl:text>Numer EORI: </xsl:text>
                        </strong>
                        <xsl:value-of select="tns:Podmiot1/tns:NrEORI"/>
                    </p>
                </xsl:if>

                <xsl:if test="tns:Podmiot1/tns:PrefiksPodatnika">
                    <p class="mb-0">
                        <strong>
                            <xsl:text>Prefiks VAT: </xsl:text>
                        </strong>
                        <xsl:value-of select="tns:Podmiot1/tns:PrefiksPodatnika"/>
                    </p>
                </xsl:if>

                <p class="mb-0">
                    <strong>
                        <xsl:text>NIP: </xsl:text>
                    </strong>
                    <xsl:value-of select="tns:Podmiot1/tns:DaneIdentyfikacyjne/tns:NIP"/>
                </p>

                <p class="mb-0">
                    <strong>
                        <xsl:text>Nazwa: </xsl:text>
                    </strong>
                    <xsl:value-of select="tns:Podmiot1/tns:DaneIdentyfikacyjne/tns:Nazwa"/>
                </p>

                <p class="mt-3 mb-0 fw-bold">
                    <xsl:text>Adres</xsl:text>
                </p>

                <p class="m-0">
                    <!-- todo address template -->
                    <xsl:value-of select="tns:Podmiot1/tns:Adres/tns:AdresL1"/>
                </p>

                <xsl:if test="tns:Podmiot1/tns:Adres/tns:AdresL2">
                    <p class="m-0">
                        <xsl:value-of select="tns:Podmiot1/tns:Adres/tns:AdresL2"/>
                    </p>
                </xsl:if>

                <p class="m-0">
                    <xsl:apply-templates select="tns:Podmiot1/tns:Adres/tns:KodKraju"/>
                </p>

                <xsl:if test="tns:Podmiot1/tns:AdresKoresp/tns:AdresL1|tns:Podmiot1/tns:AdresKoresp/tns:AdresL2">
                    <p class="mt-3 mb-0 fw-bold">
                        <xsl:text>Adres do korespondencji</xsl:text>
                    </p>

                    <p class="m-0">
                        <xsl:value-of select="tns:Podmiot1/tns:AdresKoresp/tns:AdresL1"/>
                    </p>

                    <xsl:if test="tns:Podmiot1/tns:AdresKoresp/tns:AdresL2">
                        <p class="m-0">
                            <xsl:value-of select="tns:Podmiot1/tns:AdresKoresp/tns:AdresL2"/>
                        </p>
                    </xsl:if>

                    <p class="m-0">
                        <xsl:apply-templates select="tns:Podmiot1/tns:AdresKoresp/tns:KodKraju"/>
                    </p>
                </xsl:if>

                <xsl:if test="tns:Podmiot1/tns:DaneKontaktowe">
                    <p class="mt-3 mb-0 fw-bold">Dane kontaktowe podatnika</p>

                    <xsl:if test="tns:Podmiot1/tns:DaneKontaktowe/tns:Email">
                        <p class="mb-0">
                            <strong>
                                <xsl:text>E-mail: </xsl:text>
                            </strong>
                            <xsl:value-of select="tns:Podmiot1/tns:DaneKontaktowe/tns:Email"/>
                        </p>
                    </xsl:if>

                    <xsl:if test="tns:Podmiot1/tns:DaneKontaktowe/tns:Telefon">
                        <p class="mb-0">
                            <strong>
                                <xsl:text>Tel.: </xsl:text>
                            </strong>
                            <xsl:value-of select="tns:Podmiot1/tns:DaneKontaktowe/tns:Telefon"/>
                        </p>
                    </xsl:if>
                </xsl:if>
            </div>

            <div class="col-6">
                <h6 class="fw-bold">Nabywca</h6>
                <xsl:if test="tns:Podmiot2/tns:NrEORI">
                    <p class="mb-0">
                        <strong>
                            <xsl:text>Numer EORI: </xsl:text>
                        </strong>
                        <xsl:value-of select="tns:Podmiot2/tns:NrEORI"/>
                    </p>
                </xsl:if>

                <xsl:if test="tns:Podmiot2/tns:PrefiksPodatnika">
                    <p class="mb-0">
                        <strong>
                            <xsl:text>Prefiks VAT: </xsl:text>
                        </strong>
                        <xsl:value-of select="tns:Podmiot2/tns:PrefiksPodatnika"/>
                    </p>
                </xsl:if>

                <p class="mb-0">
                    <strong>
                        <xsl:text>NIP: </xsl:text>
                    </strong>
                    <xsl:value-of select="tns:Podmiot2/tns:DaneIdentyfikacyjne/tns:NIP"/>
                </p>

                <p class="mb-0">
                    <strong>
                        <xsl:text>Nazwa: </xsl:text>
                    </strong>
                    <xsl:value-of select="tns:Podmiot2/tns:DaneIdentyfikacyjne/tns:Nazwa"/>
                </p>

                <p class="mt-3 mb-0 fw-bold">
                    <xsl:text>Adres</xsl:text>
                </p>

                <p class="m-0">
                    <xsl:value-of select="tns:Podmiot2/tns:Adres/tns:AdresL1"/>
                </p>

                <xsl:if test="tns:Podmiot2/tns:Adres/tns:AdresL2">
                    <p class="m-0">
                        <xsl:value-of select="tns:Podmiot2/tns:Adres/tns:AdresL2"/>
                    </p>
                </xsl:if>

                <p class="m-0">
                    <xsl:apply-templates select="tns:Podmiot2/tns:Adres/tns:KodKraju"/>
                </p>

                <xsl:if test="tns:Podmiot2/tns:AdresKoresp/tns:AdresL1|tns:Podmiot2/tns:AdresKoresp/tns:AdresL2">
                    <p class="mt-3 mb-0 fw-bold">
                        <xsl:text>Adres do korespondencji</xsl:text>
                    </p>

                    <p class="m-0">
                        <xsl:value-of select="tns:Podmiot2/tns:AdresKoresp/tns:AdresL1"/>
                    </p>

                    <xsl:if test="tns:Podmiot2/tns:AdresKoresp/tns:AdresL2">
                        <p class="m-0">
                            <xsl:value-of select="tns:Podmiot2/tns:AdresKoresp/tns:AdresL2"/>
                        </p>
                    </xsl:if>

                    <p class="m-0">
                        <xsl:apply-templates select="tns:Podmiot2/tns:AdresKoresp/tns:KodKraju"/>
                    </p>
                </xsl:if>

                <xsl:if test="tns:Podmiot2/tns:DaneKontaktowe">
                    <p class="mt-3 mb-0 fw-bold">Dane kontaktowe nabywcy</p>

                    <xsl:if test="tns:Podmiot2/tns:DaneKontaktowe/tns:Email">
                        <p class="mb-0">
                            <strong>
                                <xsl:text>E-mail: </xsl:text>
                            </strong>
                            <xsl:value-of select="tns:Podmiot2/tns:DaneKontaktowe/tns:Email"/>
                        </p>
                    </xsl:if>

                    <xsl:if test="tns:Podmiot2/tns:DaneKontaktowe/tns:Telefon">
                        <p class="mb-0">
                            <strong>
                                <xsl:text>Tel.: </xsl:text>
                            </strong>
                            <xsl:value-of select="tns:Podmiot2/tns:DaneKontaktowe/tns:Telefon"/>
                        </p>
                    </xsl:if>
                </xsl:if>
            </div>
        </div>
        <hr/>
    </xsl:template>

    <xsl:template name="FakturaWiersze">
        <xsl:if test="tns:Fa/tns:FaWiersz|tns:Fa/tns:Zamowienie">
            <xsl:variable name="TypCen">
                <xsl:choose>
                    <xsl:when test="tns:Fa/tns:FaWiersz/tns:P_9A">
                        netto
                    </xsl:when>
                    <xsl:otherwise>
                        brutto
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:variable>

            <xsl:variable name="StanPrzed" select="boolean(tns:Fa/tns:FaWiersz/tns:StanPrzed)"/>

            <h6 class="fw-bold">Pozycje</h6>
            <p class="mb-0">
                Faktura wystawiona w cenach
                <xsl:value-of select="$TypCen"/>
                w walucie
                <xsl:value-of select="tns:Fa/tns:KodWaluty"/>
            </p>

            <xsl:if test="tns:Fa/tns:Zamowienie/tns:WartoscZamowienia">
                <p class="mb-0">
                    Wartość zamówienia lub umowy z uwzględnieniem kwoty podatku:
                    <xsl:value-of select="tns:Fa/tns:Zamowienie/tns:WartoscZamowienia"/>
                </p>
            </xsl:if>

            <table class="table table-sm table-bordered mt-3">
                <tr class="bg-100 fw-bold">
                    <td>Lp.</td>
                    <td>Nazwa towaru lub usługi</td>
                    <td>
                        Cena jedn.
                        <xsl:value-of select="$TypCen"/>
                    </td>
                    <td>Ilość</td>
                    <td>Miara</td>
                    <td>Stawka podatku</td>
                    <td>
                        Wartość sprzedaży
                        <xsl:value-of select="$TypCen"/>
                    </td>

                    <xsl:if test="tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz/tns:P_11VatZ">
                        <td>Kwota podatku</td>
                    </xsl:if>

                    <xsl:if test="$StanPrzed">
                        <td>Stan przed</td>
                    </xsl:if>
                </tr>

                <xsl:for-each select="tns:Fa/tns:FaWiersz|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz">
                    <tr>
                        <td>
                            <xsl:value-of select="tns:NrWierszaFa|tns:NrWierszaZam"/>
                        </td>

                        <td>
                            <xsl:value-of select="tns:P_7|tns:P_7Z"/>
                        </td>

                        <td class="text-end">
                            <xsl:value-of select="tns:P_9A|tns:P_9B|tns:P_9AZ"/>
                        </td>

                        <td class="text-end">
                            <xsl:value-of select="tns:P_8B|tns:P_8BZ"/>
                        </td>

                        <td>
                            <xsl:value-of select="tns:P_8A|tns:P_8AZ"/>
                        </td>

                        <td>
                            <xsl:choose>
                                <xsl:when test="(tns:P_12|tns:P_12Z) = '23'">
                                    <xsl:text>23%</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = '22'">
                                    <xsl:text>22%</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = '8'">
                                    <xsl:text>8%</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = '7'">
                                    <xsl:text>7%</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = '5'">
                                    <xsl:text>5%</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = '4'">
                                    <xsl:text>4%</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = '3'">
                                    <xsl:text>3%</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = '0 KR'">
                                    <xsl:text>
                                        0% w przypadku sprzedaży towarów i świadczenia usług na terytorium kraju
                                        (z wyłączeniem WDT i eksportu)
                                    </xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = '0 WDT'">
                                    <xsl:text>0% w przypadku wewnątrzwspólnotowej dostawy towarów (WDT)</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = '0 EX'">
                                    <xsl:text>0% w przypadku eksportu towarów</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = 'zw'">
                                    <xsl:text>zwolnione od podatku</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = 'oo'">
                                    <xsl:text>odwrotne obciążenie</xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = 'np I'">
                                    <xsl:text>
                                        niepodlegające opodatkowaniu - dostawy towarów oraz świadczenia usług poza
                                        terytorium kraju, z wyłączeniem transakcji, o których mowa w art. 100 ust.
                                        1 pkt 4 ustawy oraz OSS
                                    </xsl:text>
                                </xsl:when>

                                <xsl:when test="(tns:P_12|tns:P_12Z) = 'np II'">
                                    <xsl:text>
                                        niepodlegające opodatkowaniu na terytorium kraju, świadczenie usług,
                                        o których mowa w art. 100 ust. 1 pkt 4 ustawy
                                    </xsl:text>
                                </xsl:when>
                            </xsl:choose>
                        </td>

                        <td class="text-end">
                            <xsl:value-of select="tns:P_11|tns:P_11A|tns:P_11NettoZ"/>
                        </td>

                        <xsl:if test="tns:P_11VatZ">
                            <td class="text-end">
                                <xsl:value-of select="tns:P_11VatZ"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$StanPrzed">
                            <td>
                                <xsl:if test="tns:StanPrzed = '1'">
                                    <xsl:text>Tak</xsl:text>
                                </xsl:if>
                            </td>
                        </xsl:if>
                    </tr>
                </xsl:for-each>
            </table>

            <h6 class="fw-bold text-end" style="color: #434A50;">
                <xsl:if test="((tns:Fa/tns:RodzajFaktury = 'VAT') or (tns:Fa/tns:RodzajFaktury = 'KOR') or (tns:Fa/tns:RodzajFaktury = 'UPR'))">
                    Kwota należności ogółem:
                </xsl:if>

                <xsl:if test="((tns:Fa/tns:RodzajFaktury = 'ZAL') or (tns:Fa/tns:RodzajFaktury = 'KOR_ZAL'))">
                    Otrzymana kwota zapłaty (zaliczki):
                </xsl:if>

                <xsl:if test="((tns:Fa/tns:RodzajFaktury = 'ROZ') or (tns:Fa/tns:RodzajFaktury = 'KOR_ROZ'))">
                    Kwota pozostała do zapłaty:
                </xsl:if>

                <xsl:value-of select="tns:Fa/tns:P_15"/>
                <xsl:text> </xsl:text>
                <xsl:value-of select="tns:Fa/tns:KodWaluty"/>
            </h6>
        </xsl:if>
    </xsl:template>

    <xsl:template name="PodliczenieVAT">
        <xsl:variable name="Podatki" select="tns:Fa/tns:P_13_1[number(.) != 0]|tns:Fa/tns:P_13_2[number(.) != 0]|tns:Fa/tns:P_13_3[number(.) != 0]|tns:Fa/tns:P_13_4[number(.) != 0]|tns:Fa/tns:P_13_5[number(.) != 0]|tns:Fa/tns:P_13_6_1[number(.) != 0]|tns:Fa/tns:P_13_6_2[number(.) != 0]|tns:Fa/tns:P_13_6_3[number(.) != 0]|tns:Fa/tns:P_13_7[number(.) != 0]|tns:Fa/tns:P_13_8[number(.) != 0]|tns:Fa/tns:P_13_9[number(.) != 0]|tns:Fa/tns:P_13_10[number(.) != 0]|tns:Fa/tns:P_13_11[number(.) != 0]"/>

        <xsl:if test="$Podatki">

            <h6 class="fw-bold">Podsumowanie stawek podatku</h6>

            <table class="table table-sm table-bordered">
                <tr class="bg-100">
                    <td class="fw-bold">Lp.</td>
                    <td class="fw-bold">Stawka podatku</td>
                    <td class="fw-bold">Kwota netto</td>
                    <td class="fw-bold">Kwota podatku</td>
                    <td class="fw-bold">Kwota brutto</td>
                    <xsl:if test="tns:Fa/tns:P_14_1W">
                        <td class="fw-bold">Kwota podatku PLN</td>
                    </xsl:if>
                </tr>

                <xsl:for-each select="$Podatki">
                    <tr>
                        <td>
                            <xsl:number/>
                        </td>

                        <td>
                            <xsl:choose>
                                <xsl:when test="self::tns:P_13_1">22% lub 23%</xsl:when>
                                <xsl:when test="self::tns:P_13_2">7% lub 8%</xsl:when>
                                <xsl:when test="self::tns:P_13_3">5%</xsl:when>
                                <xsl:when test="self::tns:P_13_6_1">0% krajowe</xsl:when>
                                <xsl:when test="self::tns:P_13_6_2">0% WDT</xsl:when>
                                <xsl:when test="self::tns:P_13_6_3">0% eksport</xsl:when>
                                <xsl:when test="self::tns:P_13_5">oss</xsl:when>
                                <xsl:when test="self::tns:P_13_7">zw</xsl:when>
                                <xsl:when test="self::tns:P_13_4">ryczałt taxi</xsl:when>

                                <xsl:when test="self::tns:P_13_8">
                                    np z wyłączeniem art. 100 ust. 1 pkt 4 ustawy
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_9">
                                    np wynikające z art. 100 ust. 1 pkt 4 ustawy
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_10">oo</xsl:when>
                                <xsl:when test="self::tns:P_13_11">marża</xsl:when>
                            </xsl:choose>
                        </td>

                        <td class="text-end">
                            <xsl:value-of select="."/>
                        </td>

                        <td class="text-end">
                            <xsl:choose>
                                <xsl:when test="self::tns:P_13_1">
                                    <xsl:value-of select="../tns:P_14_1"/>
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_2">
                                    <xsl:value-of select="../tns:P_14_2"/>
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_3">
                                    <xsl:value-of select="../tns:P_14_3"/>
                                </xsl:when>

                                <xsl:otherwise>
                                    <xsl:text>0.00</xsl:text>
                                </xsl:otherwise>
                            </xsl:choose>
                        </td>

                        <td class="text-end">
                            <xsl:value-of select="../tns:P_15"/>
                        </td>

                        <xsl:if test="../tns:P_14_1W">
                            <td class="text-end">
                                <xsl:value-of select="../tns:P_14_1W"/>
                            </td>
                        </xsl:if>
                    </tr>
                </xsl:for-each>
            </table>
            <hr/>
        </xsl:if>
    </xsl:template>

    <xsl:template name="Adnotacje">
        <xsl:for-each select="tns:Fa/tns:Adnotacje">
            <h6 class="fw-bold">Adnotacje</h6>
            <div class="row">
                <xsl:for-each select="tns:Zwolnienie">
                    <xsl:if test="tns:P_19">
                        <xsl:if test="tns:P_19 = '1'">
                            <div class="col-6">
                                Dostawa towarów lub świadczenie usług zwolnionych od podatku na podstawie
                                art. 43 ust. 1, art. 113 ust. 1 i 9 albo przepisów wydanych na podstawie art. 82
                                ust. 3 lub na podstawie innych przepisów
                            </div>

                            <xsl:if test="tns:P_19A|tns:P_19B|tns:P_19C">
                                <xsl:if test="tns:P_19B">
                                    <div class="col-6">
                                        <strong>Podstawa zwolnienia od podatku: </strong>
                                        Przepis dyrektywy 2006/112/WE, który zwalnia od podatku taką dostawę towarów
                                        lub takie świadczenie usług
                                    </div>
                                </xsl:if>

                                <div class="col-6">
                                    <strong>Przepis dyrektywy: </strong>
                                    <xsl:choose>
                                        <xsl:when test="tns:P_19A">
                                            <xsl:value-of select="tns:P_19A"/>
                                        </xsl:when>

                                        <xsl:when test="tns:P_19B">
                                            <xsl:value-of select="tns:P_19B"/>
                                        </xsl:when>

                                        <xsl:when test="tns:P_19C">
                                            <xsl:value-of select="tns:P_19C"/>
                                        </xsl:when>
                                    </xsl:choose>
                                </div>
                            </xsl:if>
                        </xsl:if>
                    </xsl:if>

                    <xsl:if test="tns:P_19N = '1'">
                        <div class="col-6">
                            Znacznik braku dostawy towarów lub świadczenia usług zwolnionych od podatku
                            na podstawie art. 43  ust. 1, art. 113 ust. 1 i 9 ustawy albo przepisów wydanych
                            na podstawie art. 82 ust. 3 ustawy lub na podstawie innych przepisów
                        </div>
                    </xsl:if>
                </xsl:for-each>
            </div>
            <xsl:if test="tns:P_16 = '1'">
                <p class="m-0">Metoda kasowa</p>
            </xsl:if>

            <xsl:if test="tns:P_17 = '1'">
                <p class="m-0">Samofakturowanie</p>
            </xsl:if>

            <xsl:if test="tns:P_18 = '1'">
                <p class="m-0">Odwrotne obciążenie</p>
            </xsl:if>

            <xsl:if test="tns:P_18A = '1'">
                <p class="m-0">Mechanizm podzielonej płatności</p>
            </xsl:if>
            <hr/>
        </xsl:for-each>
    </xsl:template>

    <xsl:template name="Platnosc">
        <xsl:for-each select="tns:Fa/tns:Platnosc">
            <h6 class="fw-bold">Płatność</h6>
            <xsl:if test="tns:Zaplacono|tns:DataZaplaty">
                <xsl:if test="tns:Zaplacono = '1'">
                    <table class="break-word" width="100%">
                        <tr>
                            <td>
                                Znacznik informujący, że należność wynikająca z faktury została zapłacona:
                                <input type="checkbox" checked="checked" disabled="disabled"/>
                                <strong>1. zapłacono</strong>
                            </td>
                        </tr>
                        <tr>
                            <td>
                                Data zapłaty, jeśli do wystawienia faktury płatność została dokonana:
                                <strong>
                                    <xsl:value-of select="tns:DataZaplaty"/>
                                </strong>
                            </td>
                        </tr>
                    </table>
                </xsl:if>
            </xsl:if>

            <div class="row">
                <div class="col-6">
                    <strong>Informacja o płatności: </strong>

                    <xsl:choose>
                        <xsl:when test="tns:Zaplacono = '1'">
                             <xsl:text>Zapłacono</xsl:text>
                        </xsl:when>

                        <xsl:otherwise>
                            <xsl:text>Brak zapłaty</xsl:text>
                        </xsl:otherwise>
                    </xsl:choose>

                    <xsl:if test="tns:FormaPlatnosci">
                        <p class="mb-0">
                            <strong>Forma płatności: </strong>
                            <xsl:choose>
                                <xsl:when test="tns:FormaPlatnosci = '1'">
                                    <xsl:text>Gotówka</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:FormaPlatnosci = '2'">
                                    <xsl:text>Karta</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:FormaPlatnosci = '3'">
                                    <xsl:text>Bon</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:FormaPlatnosci = '4'">
                                    <xsl:text>Czek</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:FormaPlatnosci = '5'">
                                    <xsl:text>Kredyt</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:FormaPlatnosci = '6'">
                                    <xsl:text>Przelew</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:FormaPlatnosci = '7'">
                                    <xsl:text>Mobilna</xsl:text>
                                </xsl:when>
                            </xsl:choose>
                        </p>
                    </xsl:if>
                </div>

                <xsl:if test="tns:TerminPlatnosci">
                    <div class="col-6">
                        <table class="table table-sm table-bordered">
                        <tr>
                            <td class="bg-100 fw-bold">Termin płatności</td>
                        </tr>
                        <xsl:for-each select="tns:TerminPlatnosci">
                            <tr>
                                <td>
                                    <xsl:value-of select="tns:Termin"/>
                                </td>
                            </tr>
                        </xsl:for-each>
                        </table>
                    </div>
                </xsl:if>
            </div>

            <xsl:if test="tns:LinkDoPlatnosci">
                <p class="mb-0">
                    <strong>Link do płatności bezgotówkowej: </strong>
                    <a href="{tns:LinkDoPlatnosci}"><xsl:value-of select="tns:LinkDoPlatnosci"/></a>
                </p>
            </xsl:if>

            <xsl:if test="tns:IPKSeF">
                <p class="mb-0">
                    <strong>Identyfikator płatności Krajowego Systemu e-Faktur: </strong>
                    <xsl:value-of select="tns:IPKSeF"/>
                </p>
            </xsl:if>

            <xsl:if test="tns:RachunekBankowy">
                <h6 class="fw-bold mt-3">Numer rachunku bankowego</h6>
                <table class="table table-sm table-bordered w-50">
                    <xsl:for-each select="tns:RachunekBankowy">
                        <tr>
                            <td class="bg-100 fw-bold">Pełny numer rachunku</td>
                            <td>
                                <xsl:value-of select="tns:NrRB"/>
                            </td>
                        </tr>

                        <xsl:if test="tns:SWIFT">
                            <tr>
                                <td class="bg-100 fw-bold">Kod SWIFT</td>
                                <td>
                                    <xsl:value-of select="tns:SWIFT"/>
                                </td>
                            </tr>
                        </xsl:if>

                        <tr>
                            <td class="bg-100 fw-bold">Rachunek własny banku</td>
                            <td>
                                <xsl:choose>
                                    <xsl:when test="tns:RachunekWlasnyBanku = '1'">
                                        <xsl:text>
                                            Rachunek banku lub rachunek spółdzielczej kasy oszczędnościowo-kredytowej
                                            służący do dokonywania rozliczeń z tytułu nabywanych przez ten bank lub tę
                                            kasę wierzytelności pieniężnych
                                        </xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:RachunekWlasnyBanku = '2'">
                                        <xsl:text>
                                            Rachunek banku lub rachunek spółdzielczej kasy oszczędnościowo-kredytowej
                                            wykorzystywany przez ten bank lub tę kasę do pobrania należności od nabywcy
                                            towarów lub usług za dostawę towarów lub świadczenie usług, potwierdzone
                                            fakturą, i przekazania jej w całości albo części dostawcy towarów lub
                                            usługodawcy
                                        </xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:RachunekWlasnyBanku = '3'">
                                        <xsl:text>
                                            Rachunek banku lub rachunek spółdzielczej kasy oszczędnościowo-kredytowej
                                            prowadzony przez ten bank lub tę kasę w ramach gospodarki własnej,
                                            niebędący rachunkiem rozliczeniowym
                                        </xsl:text>
                                    </xsl:when>
                                </xsl:choose>
                            </td>
                        </tr>
                        <tr>
                            <td class="bg-100 fw-bold">Nazwa banku</td>
                            <td>
                                <xsl:value-of select="tns:NazwaBanku"/>
                            </td>
                        </tr>

                        <tr>
                            <td class="bg-100 fw-bold">Opis rachunku</td>
                            <td>
                                <xsl:value-of select="tns:OpisRachunku"/>
                            </td>
                        </tr>
                    </xsl:for-each>
                </table>
            </xsl:if>
            <hr/>
        </xsl:for-each>
    </xsl:template>

    <xsl:template name="WarunkiTransakcji">
        <xsl:for-each select="tns:Fa/tns:WarunkiTransakcji">
            <h6 class="fw-bold">Warunki transakcji</h6>
            <div class="row">
                <xsl:if test="tns:Zamowienia">
                    <xsl:variable name="DataZamowienia" select="boolean(tns:Zamowienia/tns:DataZamowienia)"/>

                    <div class="col-6 offset-6">
                        <strong>Zamówienie</strong>

                        <table class="table table-sm table-bordered">
                        <tr>
                            <xsl:if test="$DataZamowienia">
                                <td class="bg-100 fw-bold">Data zamówienia</td>
                            </xsl:if>

                            <td class="bg-100 fw-bold">Numer zamówienia</td>
                        </tr>

                        <xsl:for-each select="tns:Zamowienia">
                            <tr>
                                <xsl:if test="$DataZamowienia">
                                    <td>
                                        <xsl:value-of select="tns:DataZamowienia"/>
                                    </td>
                                </xsl:if>

                                <td>
                                    <xsl:if test="tns:NrZamowienia">
                                        <xsl:value-of select="tns:NrZamowienia"/>
                                    </xsl:if>
                                </td>
                            </tr>
                        </xsl:for-each>
                        </table>
                    </div>
                </xsl:if>
            </div>
            <hr/>
        </xsl:for-each>
    </xsl:template>

    <xsl:template name="WZ">
        <xsl:if test="tns:Fa/tns:WZ">
            <h6 class="fw-bold">Numery dokumentów magazynowych WZ</h6>
            <table class="table table-sm table-bordered w-50">
                <tr>
                    <td class="bg-100 fw-bold">Numer WZ</td>
                </tr>

                <xsl:for-each select="tns:Fa/tns:WZ">
                    <tr>
                        <td>
                            <xsl:value-of select="."/>
                        </td>
                    </tr>
                </xsl:for-each>
            </table>
            <hr/>
        </xsl:if>
    </xsl:template>

    <xsl:template match="*[local-name()='KodKraju']">
        <xsl:variable name="kod" select="normalize-space(.)"/>
        <xsl:variable name="nazwa" select="document($schema-krajow)//xsd:simpleType[@name='TKodKraju']//xsd:enumeration[@value = $kod]/xsd:annotation/xsd:documentation"/>

        <xsl:choose>
            <xsl:when test="string($nazwa)">
                <xsl:value-of select="$nazwa"/>
            </xsl:when>

            <xsl:otherwise>
                <xsl:value-of select="$kod"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

</xsl:stylesheet>
