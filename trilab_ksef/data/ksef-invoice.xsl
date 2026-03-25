<?xml version="1.0" encoding="UTF-8" ?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:tns="http://crd.gov.pl/wzor/2025/06/25/13775/"
                xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                xmlns:exsl="http://exslt.org/common"
                extension-element-prefixes="exsl"
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
        <xsl:call-template name="InnyPodmiot"/>
        <xsl:call-template name="Szczegoly"/>
        <xsl:call-template name="FakturaWiersze"/>
        <xsl:call-template name="PodliczenieVAT"/>
        <xsl:call-template name="Adnotacje"/>
        <xsl:call-template name="DodatkowyOpis"/>
        <xsl:call-template name="Rozliczenie"/>
        <xsl:call-template name="Platnosc"/>
        <xsl:call-template name="WarunkiTransakcji"/>
        <xsl:call-template name="WZ"/>
        <xsl:call-template name="Stopka"/>
    </xsl:template>

    <xsl:template name="PrzyczynaKorekty">
        <xsl:for-each select="tns:Fa">
            <xsl:if test="tns:PrzyczynaKorekty|tns:TypKorekty|tns:DaneFaKorygowanej">
                <div class="row">
                    <div class="col-6">
                        <xsl:if test="tns:PrzyczynaKorekty|tns:TypKorekty">
                            <h6 class="font-weight-bold">Dane faktury korygowanej</h6>

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
                        </xsl:if>
                    </div>

                    <div class="col-6">
                        <xsl:if test="tns:DaneFaKorygowanej">
                            <h6 class="font-weight-bold">Dane identyfikacyjne faktury korygowanej</h6>
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

                                <xsl:if test="tns:NrKSeFFaKorygowanej">
                                    <p class="mb-0">
                                        <strong>
                                            <xsl:text>Numer KSeF faktury korygowanej: </xsl:text>
                                        </strong>
                                        <xsl:value-of select="tns:NrKSeFFaKorygowanej"/>
                                    </p>
                                </xsl:if>
                            </xsl:for-each>
                        </xsl:if>
                    </div>
                </div>
                <hr/>
            </xsl:if>
        </xsl:for-each>
    </xsl:template>

    <xsl:template name="SprzedawcaNabywca">
        <div class="row">
            <div class="col-6">
                <h6 class="font-weight-bold">Sprzedawca</h6>
                <xsl:apply-templates select="tns:Podmiot1"/>
                <p class="mt-3 mb-0 font-weight-bold">
                    <xsl:text>Adres</xsl:text>
                </p>

                <xsl:apply-templates select="tns:Podmiot1/tns:Adres"/>

                <xsl:if test="tns:Podmiot1/tns:AdresKoresp">
                    <p class="mt-3 mb-0 font-weight-bold">
                        <xsl:text>Adres do korespondencji</xsl:text>
                    </p>

                    <xsl:apply-templates select="tns:Podmiot1/tns:AdresKoresp"/>
                </xsl:if>

                <xsl:if test="tns:Podmiot1/tns:DaneKontaktowe/node()">
                    <p class="mt-3 mb-0 font-weight-bold">Dane kontaktowe</p>
                    <xsl:apply-templates select="tns:Podmiot1/tns:DaneKontaktowe"/>
                </xsl:if>

                <xsl:if test="tns:Podmiot1/tns:StatusInfoPodatnika/node()">
                    <xsl:if test="tns:Podmiot1/tns:StatusInfoPodatnika">
                        <p class="mb-0">
                            <strong>
                                <xsl:text>Status podatnika: </xsl:text>
                            </strong>

                            <xsl:choose>
                                <xsl:when test="tns:Podmiot1/tns:StatusInfoPodatnika = '1'">
                                    <xsl:text>Stan likwidacji</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:Podmiot1/tns:StatusInfoPodatnika = '2'">
                                    <xsl:text>Postępowanie restrukturyzacyjne</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:Podmiot1/tns:StatusInfoPodatnika = '3'">
                                    <xsl:text>Stan upadłości</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:Podmiot1/tns:StatusInfoPodatnika = '4'">
                                    <xsl:text>Przedsiębiorstwo w spadku</xsl:text>
                                </xsl:when>
                            </xsl:choose>
                        </p>
                    </xsl:if>
                </xsl:if>
            </div>

            <div class="col-6">
                <h6 class="font-weight-bold">Nabywca</h6>
                <xsl:apply-templates select="tns:Podmiot2"/>

                <p class="mt-3 mb-0 font-weight-bold">
                    <xsl:text>Adres</xsl:text>
                </p>

                <xsl:apply-templates select="tns:Podmiot2/tns:Adres"/>

                <xsl:if test="tns:Podmiot2/tns:AdresKoresp">
                    <p class="mt-3 mb-0 font-weight-bold">
                        <xsl:text>Adres do korespondencji</xsl:text>
                    </p>

                    <xsl:apply-templates select="tns:Podmiot2/tns:AdresKoresp"/>
                </xsl:if>

                <xsl:if test="(tns:Podmiot2/tns:DaneKontaktowe|tns:Podmiot2/tns:NrKlienta)/node()">
                    <p class="mt-3 mb-0 font-weight-bold">Dane kontaktowe</p>
                    <xsl:apply-templates select="tns:Podmiot2/tns:DaneKontaktowe"/>

                    <xsl:if test="tns:Podmiot2/tns:NrKlienta">
                        <p class="mb-0">
                            <strong>
                                <xsl:text>Numer klienta: </xsl:text>
                            </strong>

                            <xsl:value-of select="tns:Podmiot2/tns:NrKlienta"/>
                        </p>
                    </xsl:if>
                </xsl:if>
            </div>
        </div>
        <hr/>
    </xsl:template>

    <xsl:template name="InnyPodmiot">
        <xsl:for-each select="tns:Podmiot3">
            <h6 class="font-weight-bold">Podmiot inny
                <xsl:number/>
            </h6>

            <div class="row">
                <div class="col-6">
                    <xsl:apply-templates select="."/>
                </div>

                <div class="col-6">
                    <xsl:if test="tns:Adres">
                        <p class="mb-0 font-weight-bold">
                            <xsl:text>Adres</xsl:text>
                        </p>

                        <xsl:apply-templates select="tns:Adres"/>
                    </xsl:if>

                    <xsl:if test="tns:AdresKoresp">
                        <p class="mt-3 mb-0 font-weight-bold">
                            <xsl:text>Adres do korespondencji</xsl:text>
                        </p>

                        <xsl:apply-templates select="tns:AdresKoresp"/>
                    </xsl:if>

                    <xsl:if test="(tns:DaneKontaktowe|tns:NrKlienta)/node()">
                        <p class="mt-3 mb-0 font-weight-bold">Dane kontaktowe</p>
                        <xsl:apply-templates select="tns:DaneKontaktowe"/>

                        <xsl:if test="tns:NrKlienta">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Numer klienta: </xsl:text>
                                </strong>

                                <xsl:value-of select="tns:NrKlienta"/>
                            </p>
                        </xsl:if>
                    </xsl:if>
                </div>
            </div>
            <hr/>
        </xsl:for-each>
    </xsl:template>

    <xsl:template name="Szczegoly">
        <xsl:variable name="SzczegolyElementy">
            <root>
                <xsl:if test="//tns:Fa/tns:P_1">
                    <item>
                        <label>Data wystawienia, z zastrzeżeniem art. 106 na ust. 1 ustawy: </label>
                        <value><xsl:value-of select="//tns:P_1"/></value>
                    </item>
                </xsl:if>

                <xsl:if test="//tns:Fa/tns:P_1M">
                   <item>
                        <label>Miejsce wystawienia: </label>
                        <value><xsl:value-of select="//tns:Fa/tns:P_1M"/></value>
                    </item>
                </xsl:if>

                <xsl:if test="//tns:Fa/tns:OkresFaKorygowanej">
                    <item>
                        <label>Okres, którego dotyczy rabat:</label>
                        <value><xsl:value-of select="//tns:Fa/tns:OkresFaKorygowanej"/></value>
                    </item>
                </xsl:if>

                <xsl:if test="//tns:Fa/tns:P_6|//tns:Fa/tns:OkresFa">
                    <item>
                        <label>
                            <xsl:choose>
                                <xsl:when test="//tns:Fa/tns:RodzajFaktury = 'ZAL' or //tns:Fa/tns:RodzajFaktury = 'KOR_ZAL'">
                                    <xsl:text>Data otrzymania zapłaty: </xsl:text>
                                </xsl:when>

                                <xsl:otherwise>
                                    <xsl:text>Data dokonania lub zakończenia dostawy towarów lub wykonania usługi: </xsl:text>
                                </xsl:otherwise>
                            </xsl:choose>
                        </label>

                        <value>
                            <xsl:choose>
                                <xsl:when test="//tns:Fa/tns:P_6">
                                    <xsl:value-of select="//tns:Fa/tns:P_6"/>
                                </xsl:when>

                                <xsl:when test="//tns:Fa/tns:OkresFa">
                                    <xsl:text>od</xsl:text>
                                    <xsl:value-of select="//tns:Fa/tns:OkresFa/tns:P_6_Od"/>
                                    <xsl:text>do</xsl:text>
                                    <xsl:value-of select="//tns:Fa/tns:OkresFa/tns:P_6_Do"/>
                                </xsl:when>
                            </xsl:choose>
                        </value>
                    </item>
                </xsl:if>

                <xsl:if test="not (//tns:Fa/tns:FaWiersz or //tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz)">
                    <item>
                        <label>Faktura wystawiona w cenach: </label>
                        <value>brutto</value>
                    </item>

                    <item>
                        <label>Kod waluty: </label>
                        <value><xsl:value-of select="tns:Fa/tns:KodWaluty"/></value>
                    </item>
                </xsl:if>

                <xsl:if test="//tns:Fa/tns:FaWiersz[tns:P_12_XII]|//tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:P_12Z_XII]">
                    <item>
                        <label>Procedura One Stop Shop</label>
                    </item>
                </xsl:if>


                <xsl:if test="tns:Fa/tns:FaWiersz[1]/tns:KursWaluty and not(tns:Fa/tns:FaWiersz/tns:KursWaluty != tns:Fa/tns:FaWiersz[1]/tns:KursWaluty)">
                    <item>
                        <label>Kurs waluty wspólny dla wszystkich wierszy faktury</label>
                    </item>

                    <item>
                        <label>Kurs waluty: </label>
                        <value><xsl:value-of select="format-number(number(//tns:Fa/tns:FaWiersz[1]/tns:KursWaluty), '0.000000')"/></value>
                    </item>
                </xsl:if>
            </root>
        </xsl:variable>

        <xsl:variable name="SzczegolyNodes" select="exsl:node-set($SzczegolyElementy)/root/item"/>

        <h6 class="font-weight-bold">Szczegóły</h6>
        <div class="row">
            <div class="col-6">
                <xsl:for-each select="$SzczegolyNodes[position() mod 2 = 1]">
                  <p class="mb-0">
                    <strong><xsl:value-of select="label"/></strong>
                    <span class="text-nowrap"><xsl:value-of select="value"/></span>
                  </p>
                </xsl:for-each>
            </div>

            <div class="col-6">
                <xsl:for-each select="$SzczegolyNodes[position() mod 2 = 0]">
                  <p class="mb-0">
                    <strong><xsl:value-of select="label"/></strong>
                    <span class="text-nowrap"><xsl:value-of select="value"/></span>
                  </p>
                </xsl:for-each>
            </div>
        </div>
        <hr/>
    </xsl:template>

    <xsl:template name="FakturaWiersze">
        <xsl:if test="tns:Fa/tns:FaWiersz|tns:Fa/tns:Zamowienie">
            <xsl:variable name="TypCen">
                <xsl:choose>
                    <xsl:when test="tns:Fa/tns:FaWiersz[tns:P_11]">
                        <xsl:text>netto</xsl:text>
                    </xsl:when>

                    <xsl:otherwise>
                        <xsl:text>brutto</xsl:text>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:variable>

            <xsl:variable name="UnikalnyNumerWiersza" select="tns:Fa/tns:FaWiersz[tns:UU_ID]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:UU_ID]"/>
            <xsl:variable name="NazwaTowaru" select="tns:Fa/tns:FaWiersz[tns:P_7]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:P_7Z]"/>
            <xsl:variable name="CenaJednostkowaNetto" select="tns:Fa/tns:FaWiersz[tns:P_9A]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:P_9AZ]"/>
            <xsl:variable name="CenaJednostkowaBrutto" select="tns:Fa/tns:FaWiersz[tns:P_9B]"/>
            <xsl:variable name="Ilosc" select="tns:Fa/tns:FaWiersz[tns:P_8B]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:P_8BZ]"/>
            <xsl:variable name="Miara" select="tns:Fa/tns:FaWiersz[tns:P_8A]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:P_8AZ]"/>
            <xsl:variable name="Rabat" select="tns:Fa/tns:FaWiersz[tns:P_10]"/>
            <xsl:variable name="StawkaPodatku" select="tns:Fa/tns:FaWiersz[tns:P_12]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:P_12Z]"/>
            <xsl:variable name="StawkaPodatkuOss" select="tns:Fa/tns:FaWiersz[tns:P_12_XII]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:P_12Z_XII]"/>
            <xsl:variable name="Zalacznik" select="tns:Fa/tns:FaWiersz[tns:P_12_Zal_15]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:P_12Z_Zal_15]"/>
            <xsl:variable name="WartoscSprzedazyNetto" select="tns:Fa/tns:FaWiersz[tns:P_11]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:P_11NettoZ]"/>
            <xsl:variable name="WartoscSprzedazyBrutto" select="tns:Fa/tns:FaWiersz[tns:P_11A]"/>
            <xsl:variable name="WartoscSprzedazyVat" select="tns:Fa/tns:FaWiersz[tns:P_11Vat]"/>
            <xsl:variable name="KwotaPodatku" select="tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:P_11VatZ]"/>
            <xsl:variable name="KursWaluty" select="tns:Fa/tns:FaWiersz/tns:KursWaluty != tns:Fa/tns:FaWiersz[1]/tns:KursWaluty"/>
            <xsl:variable name="StanPrzed" select="tns:Fa/tns:FaWiersz[tns:StanPrzed = '1']"/>

            <h6 class="font-weight-bold">
                <xsl:choose>
                    <xsl:when test="tns:Fa/tns:Zamowienie">
                        <xsl:text>Zamówienie</xsl:text>
                    </xsl:when>

                    <xsl:otherwise>
                        <xsl:text>Pozycje</xsl:text>
                    </xsl:otherwise>
                </xsl:choose>
            </h6>
            <p class="mb-0">
                Faktura wystawiona w cenach
                <xsl:value-of select="$TypCen"/>
                w walucie
                <xsl:value-of select="tns:Fa/tns:KodWaluty"/>
            </p>

            <xsl:if test="tns:Fa/tns:Zamowienie/tns:WartoscZamowienia">
                <p class="mb-0">
                    Wartość zamówienia lub umowy z uwzględnieniem kwoty podatku:
                    <xsl:value-of select="format-number(number(tns:Fa/tns:Zamowienie/tns:WartoscZamowienia), '0.00')"/>
                </p>
            </xsl:if>

            <table class="table table-sm table-bordered mt-3" style="table-layout: auto;">
                <tr class="bg-100 font-weight-bold text-nowrap">
                    <td>Lp.</td>

                    <xsl:if test="$UnikalnyNumerWiersza">
                        <td>Unikalny numer wiersza</td>
                    </xsl:if>

                    <xsl:if test="$NazwaTowaru">
                        <td>Nazwa towaru lub usługi</td>
                    </xsl:if>

                    <xsl:if test="$CenaJednostkowaNetto">
                        <td>Cena jedn. netto</td>
                    </xsl:if>

                    <xsl:if test="$CenaJednostkowaBrutto">
                        <td>Cena jedn. brutto</td>
                    </xsl:if>

                    <xsl:if test="$Rabat">
                        <td>Rabat</td>
                    </xsl:if>

                    <xsl:if test="$Ilosc">
                        <td>Ilość</td>
                    </xsl:if>

                    <xsl:if test="$Miara">
                        <td>Miara</td>
                    </xsl:if>

                    <xsl:if test="$StawkaPodatku">
                        <td>Stawka podatku</td>
                    </xsl:if>

                    <xsl:if test="$StawkaPodatkuOss">
                        <td>Stawka podatku OSS</td>
                    </xsl:if>

                    <xsl:if test="$Zalacznik">
                        <td>Znacznik dla towaru lub usługi z zał. nr 15 do ustawy</td>
                    </xsl:if>

                    <xsl:if test="$WartoscSprzedazyNetto">
                        <td>Wartość sprzedaży netto</td>
                    </xsl:if>

                    <xsl:if test="$WartoscSprzedazyBrutto">
                        <td>Wartość sprzedaży brutto</td>
                    </xsl:if>

                    <xsl:if test="$WartoscSprzedazyVat">
                        <td>Wartość sprzedaży vat</td>
                    </xsl:if>

                    <xsl:if test="$KwotaPodatku">
                        <td>Kwota podatku</td>
                    </xsl:if>

                    <xsl:if test="$KursWaluty">
                        <td>Kurs waluty</td>
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

                        <xsl:if test="$UnikalnyNumerWiersza">
                            <td><xsl:value-of select="tns:UU_ID"/></td>
                        </xsl:if>

                        <xsl:if test="$NazwaTowaru">
                            <td>
                                <xsl:value-of select="tns:P_7|tns:P_7Z"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$CenaJednostkowaNetto">
                            <td class="text-right">
                                <xsl:choose>
                                    <xsl:when test="../tns:ZamowienieWiersz">
                                        <xsl:value-of select="format-number(number(tns:P_9AZ), '0.00')"/>
                                    </xsl:when>

                                    <xsl:otherwise>
                                        <xsl:value-of select="format-number(number(tns:P_9A), '0.00')"/>
                                    </xsl:otherwise>
                                </xsl:choose>
                            </td>
                        </xsl:if>

                        <xsl:if test="$CenaJednostkowaBrutto">
                            <td class="text-right">
                                <xsl:value-of select="format-number(number(tns:P_9B), '0.00')"/>
                            </td>
                        </xsl:if>


                        <xsl:if test="$Ilosc">
                            <td class="text-right">
                                <xsl:choose>
                                    <xsl:when test="../tns:ZamowienieWiersz">
                                        <xsl:value-of select="tns:P_8BZ"/>
                                    </xsl:when>

                                    <xsl:otherwise>
                                        <xsl:value-of select="tns:P_8B"/>
                                    </xsl:otherwise>
                                </xsl:choose>
                            </td>
                        </xsl:if>

                        <xsl:if test="$Miara">
                            <td>
                                <xsl:choose>
                                    <xsl:when test="../tns:ZamowienieWiersz">
                                        <xsl:value-of select="tns:P_8AZ"/>
                                    </xsl:when>

                                    <xsl:otherwise>
                                        <xsl:value-of select="tns:P_8A"/>
                                    </xsl:otherwise>
                                </xsl:choose>
                            </td>
                        </xsl:if>

                        <xsl:if test="$Rabat">
                            <td class="text-right">
                                <xsl:value-of select="tns:P_10"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$StawkaPodatku">
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
                                        <xsl:text>0% - KR</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="(tns:P_12|tns:P_12Z) = '0 WDT'">
                                        <xsl:text>0% - WDT</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="(tns:P_12|tns:P_12Z) = '0 EX'">
                                        <xsl:text>0% - EX</xsl:text>
                                    </xsl:when>

                                    <xsl:otherwise>
                                        <xsl:value-of select="tns:P_12|tns:P_12Z"/>
                                    </xsl:otherwise>
                                </xsl:choose>
                            </td>
                        </xsl:if>

                        <xsl:if test="$StawkaPodatkuOss">
                            <td>
                                <xsl:choose>
                                    <xsl:when test="../tns:ZamowienieWiersz">
                                        <xsl:value-of select="tns:P_12Z_XII"/>
                                    </xsl:when>

                                    <xsl:otherwise>
                                        <xsl:value-of select="tns:P_12_XII"/>
                                    </xsl:otherwise>
                                </xsl:choose>
                                <xsl:text>%</xsl:text>
                            </td>
                        </xsl:if>

                        <xsl:if test="$Zalacznik">
                            <td>
                                <xsl:choose>
                                    <xsl:when test="../tns:ZamowienieWiersz">
                                        <xsl:value-of select="tns:P_12Z_Zal_15"/>
                                    </xsl:when>

                                    <xsl:otherwise>
                                        <xsl:value-of select="tns:P_12_Zal_15"/>
                                    </xsl:otherwise>
                                </xsl:choose>
                            </td>
                        </xsl:if>

                        <xsl:if test="$WartoscSprzedazyNetto">
                            <td class="text-right">
                                <xsl:choose>
                                    <xsl:when test="../tns:ZamowienieWiersz">
                                        <xsl:value-of select="format-number(number(tns:P_11NettoZ), '0.00')"/>
                                    </xsl:when>

                                    <xsl:otherwise>
                                        <xsl:value-of select="format-number(number(tns:P_11), '0.00')"/>
                                    </xsl:otherwise>
                                </xsl:choose>
                            </td>
                        </xsl:if>

                        <xsl:if test="$WartoscSprzedazyBrutto">
                            <td class="text-right">
                                <xsl:value-of select="format-number(number(tns:P_11A), '0.00')"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$WartoscSprzedazyVat">
                            <td class="text-right">
                                <xsl:value-of select="format-number(number(tns:P_11Vat), '0.00')"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$KwotaPodatku">
                            <td class="text-right">
                                <xsl:value-of select="format-number(number(tns:P_11VatZ), '0.00')"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$KursWaluty">
                            <td class="text-right">
                                <xsl:value-of select="format-number(number(tns:KursWaluty), '0.000000')"/>
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

            <xsl:call-template name="SzczegolyPozycji"/>

            <h6 class="font-weight-bold text-right">
                <xsl:choose>
                    <xsl:when test="tns:Fa/tns:RodzajFaktury = 'VAT' or tns:Fa/tns:RodzajFaktury = 'KOR' or tns:Fa/tns:RodzajFaktury = 'UPR'">
                        <xsl:text>Kwota należności ogółem: </xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Fa/tns:RodzajFaktury = 'ZAL' or tns:Fa/tns:RodzajFaktury = 'KOR_ZAL'">
                        <xsl:text>Otrzymana kwota zapłaty (zaliczki): </xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Fa/tns:RodzajFaktury = 'ROZ' or tns:Fa/tns:RodzajFaktury = 'KOR_ROZ'">
                        <xsl:text>Kwota pozostała do zapłaty: </xsl:text>
                    </xsl:when>
                </xsl:choose>

                <xsl:value-of select="format-number(number(tns:Fa/tns:P_15), '0.00')"/>
                <xsl:text> </xsl:text>
                <xsl:value-of select="tns:Fa/tns:KodWaluty"/>
            </h6>
        </xsl:if>
    </xsl:template>

    <xsl:template name="SzczegolyPozycji">
        <xsl:variable name="NumerUmowy" select="tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:UU_IDZ]"/>
        <xsl:variable name="GTIN" select="tns:Fa/tns:FaWiersz[tns:GTIN]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:GTINZ]"/>
        <xsl:variable name="PKWiU" select="tns:Fa/tns:FaWiersz[tns:PKWiU]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:PKWiUZ]"/>
        <xsl:variable name="CN" select="tns:Fa/tns:FaWiersz[tns:CN]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:CNZ]"/>
        <xsl:variable name="PKOB" select="tns:Fa/tns:FaWiersz[tns:PKOB]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:PKOBZ]"/>
        <xsl:variable name="KwotaAkcyzy" select="tns:Fa/tns:FaWiersz[tns:KwotaAkcyzy]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:KwotaAkcyzyZ]"/>
        <xsl:variable name="GTU" select="tns:Fa/tns:FaWiersz[tns:GTU]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:GTUZ]"/>
        <xsl:variable name="Procedura" select="tns:Fa/tns:FaWiersz[tns:Procedura]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:ProceduraZ]"/>
        <xsl:variable name="DataDostawy" select="tns:Fa/tns:FaWiersz[tns:P_6A]"/>
        <xsl:variable name="Indeks" select="tns:Fa/tns:FaWiersz[tns:Indeks]|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:IndeksZ]"/>
        <xsl:variable name="StanPrzedZ" select="tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz[tns:StanPrzedZ = '1']"/>

        <xsl:if test="$NumerUmowy|$GTIN|$PKWiU|$CN|$PKOB|$KwotaAkcyzy|$GTU|$Procedura|$DataDostawy|$Indeks|$StanPrzedZ">
            <table class="table table-sm table-bordered w-auto">
                <tr class="bg-100 font-weight-bold text-nowrap">
                    <td>Lp.</td>

                    <xsl:if test="$NumerUmowy">
                        <td>Numer umowy/Zamów.</td>
                    </xsl:if>

                    <xsl:if test="$GTIN">
                        <td>GTIN</td>
                    </xsl:if>

                    <xsl:if test="$PKWiU">
                        <td>PKWiU</td>
                    </xsl:if>

                    <xsl:if test="$CN">
                        <td>CN</td>
                    </xsl:if>

                    <xsl:if test="$PKOB">
                        <td>PKOB</td>
                    </xsl:if>

                    <xsl:if test="$KwotaAkcyzy">
                        <td>Kwota podatku akcyzowego</td>
                    </xsl:if>

                    <xsl:if test="$GTU">
                        <td>GTU</td>
                    </xsl:if>

                    <xsl:if test="$Procedura">
                        <td>Oznaczenia dotyczące procedur</td>
                    </xsl:if>

                    <xsl:if test="$DataDostawy">
                        <td>Data dostawy/wykonania</td>
                    </xsl:if>

                    <xsl:if test="$Indeks">
                        <td>Indeks</td>
                    </xsl:if>

                    <xsl:if test="$StanPrzedZ">
                        <td>Stan przed</td>
                    </xsl:if>
                </tr>

                <xsl:for-each select="tns:Fa/tns:FaWiersz|tns:Fa/tns:Zamowienie/tns:ZamowienieWiersz">
                    <tr>
                        <td>
                            <xsl:value-of select="tns:NrWierszaFa|tns:NrWierszaZam"/>
                        </td>

                        <xsl:if test="$NumerUmowy">
                            <td>
                                <xsl:value-of select="tns:UU_IDZ"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$GTIN">
                            <td>
                                <xsl:value-of select="tns:GTIN|tns:GTINZ"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$PKWiU">
                            <td>
                                <xsl:value-of select="tns:PKWiU|tns:PKWiUZ"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$CN">
                            <td>
                                <xsl:value-of select="tns:CN|tns:CNZ"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$PKOB">
                            <td>
                                <xsl:value-of select="tns:PKOB|tns:PKOBZ"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$KwotaAkcyzy">
                            <td class="text-right">
                                <xsl:choose>
                                    <xsl:when test="../tns:ZamowienieWiersz">
                                        <xsl:value-of select="format-number(number(tns:KwotaAkcyzyZ), '0.00')"/>
                                    </xsl:when>

                                    <xsl:otherwise>
                                        <xsl:value-of select="format-number(number(tns:KwotaAkcyzy), '0.00')"/>
                                    </xsl:otherwise>
                                </xsl:choose>
                            </td>
                        </xsl:if>

                        <xsl:if test="$GTU">
                            <td>
                                <xsl:value-of select="tns:GTU|tns:GTUZ"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$Procedura">
                            <td>
                                <xsl:value-of select="tns:Procedura|tns:ProceduraZ"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$DataDostawy">
                            <td>
                                <xsl:value-of select="tns:P_6A"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$Indeks">
                            <td>
                                <xsl:value-of select="tns:Indeks|IndeksZ"/>
                            </td>
                        </xsl:if>

                        <xsl:if test="$StanPrzedZ">
                            <td>
                                <xsl:if test="tns:StanPrzedZ = '1'">
                                    <xsl:text>Tak</xsl:text>
                                </xsl:if>
                            </td>
                        </xsl:if>
                    </tr>
                </xsl:for-each>
            </table>
        </xsl:if>
    </xsl:template>

    <xsl:template name="PodliczenieVAT">
        <xsl:variable name="Podatki"
                      select="tns:Fa/tns:P_13_1[number(.) != 0]|tns:Fa/tns:P_13_2[number(.) != 0]|tns:Fa/tns:P_13_3[number(.) != 0]|tns:Fa/tns:P_13_4[number(.) != 0]|tns:Fa/tns:P_13_5[number(.) != 0]|tns:Fa/tns:P_13_6_1[number(.) != 0]|tns:Fa/tns:P_13_6_2[number(.) != 0]|tns:Fa/tns:P_13_6_3[number(.) != 0]|tns:Fa/tns:P_13_7[number(.) != 0]|tns:Fa/tns:P_13_8[number(.) != 0]|tns:Fa/tns:P_13_9[number(.) != 0]|tns:Fa/tns:P_13_10[number(.) != 0]|tns:Fa/tns:P_13_11[number(.) != 0]"/>
        <xsl:variable name="PodatekPln"
                      select="tns:Fa/tns:P_14_1W|tns:Fa/tns:P_14_2W|tns:Fa/tns:P_14_3W|tns:Fa/tns:P_14_4W"/>

        <xsl:if test="$Podatki">
            <h6 class="font-weight-bold">Podsumowanie stawek podatku</h6>

            <table class="table table-sm table-bordered" style="table-layout: auto;">
                <tr class="bg-100 font-weight-bold text-nowrap">
                    <td>Lp.</td>
                    <td>Stawka podatku</td>
                    <td>Kwota netto</td>
                    <td>Kwota podatku</td>
                    <td>Kwota brutto</td>

                    <xsl:if test="$PodatekPln">
                        <td>Kwota podatku PLN</td>
                    </xsl:if>
                </tr>

                <xsl:for-each select="$Podatki">
                    <xsl:variable name="index" select="position()"/>
                    <tr>
                        <td>
                            <xsl:value-of select="$index"/>
                        </td>

                        <td>
                            <xsl:choose>
                                <xsl:when test="self::tns:P_13_1">23% lub 22%</xsl:when>
                                <xsl:when test="self::tns:P_13_2">8% lub 7%</xsl:when>
                                <xsl:when test="self::tns:P_13_3">5%</xsl:when>
                                <xsl:when test="self::tns:P_13_4">4% lub 3%</xsl:when>
                                <xsl:when test="self::tns:P_13_5">OSS</xsl:when>

                                <xsl:when test="self::tns:P_13_6_1">
                                    0% w przypadku sprzedaży towarów i świadczenia usług na terytorium kraju
                                    (z wyłączeniem WDT i eksportu)
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_6_2">
                                    0% w przypadku wewnątrzwspólnotowej dostawy towarów (WDT)
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_6_3">0% w przypadku eksportu towarów</xsl:when>
                                <xsl:when test="self::tns:P_13_7">zwolnione od podatku</xsl:when>

                                <xsl:when test="self::tns:P_13_8">
                                    np z wyłączeniem art. 100 ust. 1 pkt 4 ustawy
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_9">
                                    np na podstawie art. 100 ust. 1 pkt 4 ustawy
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_10">odwrotne obciążenie</xsl:when>
                                <xsl:when test="self::tns:P_13_11">marża</xsl:when>
                            </xsl:choose>
                        </td>

                        <td class="text-right">
                            <xsl:value-of select="format-number(number(.), '0.00')"/>
                        </td>

                        <td class="text-right">
                            <xsl:choose>
                                <xsl:when test="self::tns:P_13_1">
                                    <xsl:value-of select="format-number(number(../tns:P_14_1), '0.00')"/>
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_2">
                                    <xsl:value-of select="format-number(number(../tns:P_14_2), '0.00')"/>
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_5">
                                    <xsl:value-of select="format-number(number(../tns:P_14_5), '0.00')"/>
                                </xsl:when>

                                <xsl:otherwise>
                                    <xsl:text>0.00</xsl:text>
                                </xsl:otherwise>
                            </xsl:choose>
                        </td>

                        <td class="text-right">
                            <xsl:choose>
                                <xsl:when test="self::tns:P_13_1">
                                    <xsl:value-of
                                            select="format-number(number(../tns:P_13_1) + number(../tns:P_14_1), '0.00')"/>
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_2">
                                    <xsl:value-of
                                            select="format-number(number(../tns:P_13_2) + number(../tns:P_14_2), '0.00')"/>
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_3">
                                    <xsl:value-of
                                            select="format-number(number(../tns:P_13_3) + number(../tns:P_14_3), '0.00')"/>
                                </xsl:when>

                                <xsl:when test="self::tns:P_13_5">
                                    <xsl:value-of
                                            select="format-number(number(../tns:P_13_5) + number(../tns:P_14_5), '0.00')"/>
                                </xsl:when>

                                <xsl:otherwise>
                                    <xsl:value-of select="format-number(number(.), '0.00')"/>
                                </xsl:otherwise>
                            </xsl:choose>
                        </td>

                        <xsl:if test="$PodatekPln">
                            <td class="text-right">
                                <xsl:value-of select="format-number(number(../tns:P_14_1W), '0.00')"/>
                            </td>
                        </xsl:if>
                    </tr>
                </xsl:for-each>
            </table>
        </xsl:if>
    </xsl:template>

    <xsl:template name="Adnotacje">
        <xsl:if test="(tns:Fa/tns:Adnotacje/*[not(*)]|tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19|tns:Fa/tns:Adnotacje/tns:PMarzy/tns:P_PMarzy) = '1'">
            <h6 class="font-weight-bold">Adnotacje</h6>
            <div class="row">
                <div class="col-6">
                    <xsl:if test="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19 = '1'">
                        <p class="m-0">
                            Dostawa towarów lub świadczenie usług zwolnionych od podatku na podstawie
                            art. 43 ust. 1, art. 113 ust. 1 i 9 albo przepisów wydanych na podstawie art. 82
                            ust. 3 lub na podstawie innych przepisów
                        </p>

                        <p class="m-0">
                            <xsl:choose>
                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19A">
                                    <strong>Przepis ustawy albo aktu wydanego na podstawie ustawy: </strong>
                                    <xsl:value-of select="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19A"/>
                                </xsl:when>

                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19B">
                                    <strong>Przepis dyrektywy: </strong>
                                    <xsl:value-of select="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19B"/>
                                </xsl:when>

                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19C">
                                    <strong>Inna podstawa prawna: </strong>
                                    <xsl:value-of select="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19C"/>
                                </xsl:when>
                            </xsl:choose>
                        </p>
                    </xsl:if>

                    <xsl:if test="tns:Fa/tns:Adnotacje/tns:NoweSrodkiTransportu/tns:P_42_5">
                        <p class="m-0">
                            <strong>Wewnątrzwspólnotowe dostawy nowych środków transportu: </strong>

                            <xsl:choose>
                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:NoweSrodkiTransportu/tns:P_42_5 = '1'">
                                    <xsl:text>Istnieje obowiązek wystawienia dokumentu VAT-22</xsl:text>
                                </xsl:when>

                                <xsl:otherwise>
                                    <xsl:text>Nie istnieje obowiązek wystawienia dokumentu VAT-22</xsl:text>
                                </xsl:otherwise>
                            </xsl:choose>
                        </p>
                    </xsl:if>

                    <xsl:if test="tns:Fa/tns:Adnotacje/tns:P_18A = '1'">
                        <p class="m-0">Mechanizm podzielonej płatności</p>
                    </xsl:if>

                    <xsl:if test="tns:Fa/tns:Adnotacje/tns:P_16 = '1'">
                        <p class="m-0">Metoda kasowa</p>
                    </xsl:if>

                    <xsl:if test="tns:Fa/tns:Adnotacje/tns:P_18 = '1'">
                        <p class="m-0">Odwrotne obciążenie</p>
                    </xsl:if>

                    <xsl:if test="tns:Fa/tns:Adnotacje/tns:P_23 = '1'">
                        <p class="m-0">Procedura trójstronna uproszczona</p>
                    </xsl:if>

                    <xsl:if test="tns:Fa/tns:Adnotacje/tns:PMarzy/tns:P_PMarzy = '1'">
                        <p class="m-0">
                            <strong>Procedura marży: </strong>

                            <xsl:choose>
                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:PMarzy/tns:P_PMarzy_2 = '1'">
                                    <xsl:text>biura podróży</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:PMarzy/tns:P_PMarzy_3_1 = '1'">
                                    <xsl:text>towary używane</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:PMarzy/tns:P_PMarzy_3_2 = '1'">
                                    <xsl:text>dzieła sztuki</xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:PMarzy/tns:P_PMarzy_3_3 = '1'">
                                    <xsl:text>przedmioty kolekcjonerskie i antyki</xsl:text>
                                </xsl:when>
                            </xsl:choose>
                        </p>
                    </xsl:if>

                    <xsl:if test="tns:Fa/tns:Adnotacje/tns:P_17 = '1'">
                        <p class="m-0">Samofakturowanie</p>
                    </xsl:if>
                </div>

                <div class="col-6">
                    <xsl:if test="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19">
                        <p class="mb-0">
                            <strong>Podstawa zwolnienia od podatku: </strong>

                            <xsl:choose>
                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19A">
                                    <xsl:text>
                                        Przepis ustawy albo aktu wydanego na podstawie ustawy, na podstawie którego
                                        podatnik stosuje zwolnienie od podatku
                                    </xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19B">
                                    <xsl:text>
                                        Przepis dyrektywy 2006/112/WE, który zwalnia od podatku taką dostawę towarów
                                        lub takie świadczenie usług
                                    </xsl:text>
                                </xsl:when>

                                <xsl:when test="tns:Fa/tns:Adnotacje/tns:Zwolnienie/tns:P_19C">
                                    <xsl:text>
                                        Inna podstawa prawna wskazującą na to, że dostawa towarów lub świadczenie
                                        usług korzysta ze zwolnienia
                                    </xsl:text>
                                </xsl:when>
                            </xsl:choose>
                        </p>
                    </xsl:if>
                </div>
            </div>
        </xsl:if>
    </xsl:template>

    <xsl:template name="DodatkowyOpis">
        <xsl:if test="tns:Fa/tns:DodatkowyOpis|tns:Fa[tns:TP|tns:FP|tns:ZwrotAkcyzy]">
            <hr/>
            <h6 class="font-weight-bold">Dodatkowe informacje</h6>

            <xsl:if test="(tns:Fa/tns:TP|tns:Fa/tns:FP|tns:Fa/tns:ZwrotAkcyzy) = '1'">
                <div class="mb-2">
                    <xsl:if test="tns:Fa/tns:TP = '1'">
                        <p class="mb-0">
                            - Istniejące powiązania między nabywcą a dokonującym dostawy towarów lub usługodawcą
                        </p>
                    </xsl:if>

                    <xsl:if test="tns:Fa/tns:FP = '1'">
                        <p class="mb-0">- Faktura, o której mowa w art. 109 ust. 3d ustawy</p>
                    </xsl:if>

                    <xsl:if test="tns:Fa/tns:ZwrotAkcyzy = '1'">
                        <p class="mb-0">
                            - Informacja dodatkowa związana ze zwrotem podatku akcyzowego zawartego w cenie oleju
                            napędowego
                        </p>
                    </xsl:if>
                </div>
            </xsl:if>

            <xsl:if test="tns:Fa/tns:DodatkowyOpis">
                <xsl:variable name="NumerWiersza" select="tns:Fa/tns:DodatkowyOpis[tns:NrWiersza]"/>
                <p class="mb-0 font-weight-bold">Dodatkowy opis</p>

                <table class="table table-sm table-bordered" style="table-layout: auto;">
                    <tr class="bg-100 font-weight-bold text-nowrap">
                        <td>Lp.</td>

                        <xsl:if test="$NumerWiersza">
                            <td>Numer wiersza</td>
                        </xsl:if>

                        <td>Rodzaj informacji</td>
                        <td>Treść informacji</td>
                    </tr>

                    <xsl:for-each select="tns:Fa/tns:DodatkowyOpis">
                        <tr>
                            <td>
                                <xsl:number/>
                            </td>

                            <xsl:if test="$NumerWiersza">
                                <td>
                                    <xsl:value-of select="tns:NrWiersza"/>
                                </td>
                            </xsl:if>

                            <td>
                                <xsl:value-of select="tns:Klucz"/>
                            </td>

                            <td>
                                <xsl:call-template name="NowaLinia">
                                    <xsl:with-param name="text" select="tns:Wartosc"/>
                                </xsl:call-template>
                            </td>
                        </tr>
                    </xsl:for-each>
                </table>
            </xsl:if>
        </xsl:if>
    </xsl:template>

    <xsl:template name="Rozliczenie">
        <xsl:if test="tns:Fa/tns:Rozliczenie/tns:Obciazenia|tns:Fa/tns:Rozliczenie/tns:Odliczenia">
            <hr/>
            <h6 class="font-weight-bold">Rozliczenie</h6>
            <div class="row">
                <div class="col-6">
                    <xsl:if test="tns:Fa/tns:Rozliczenie/tns:Obciazenia">
                        <strong>Obciążenia</strong>
                        <table class="table table-sm table-bordered">
                            <tr class="bg-100 font-weight-bold text-nowrap">
                                <td>Powód obciązenia</td>
                                <td>Kwota obciązenia</td>
                            </tr>

                            <xsl:for-each select="tns:Fa/tns:Rozliczenie/tns:Obciazenia">
                                <tr>
                                    <td>
                                        <xsl:value-of select="tns:Powod"/>
                                    </td>

                                    <td class="text-right">
                                        <xsl:value-of select="format-number(number(tns:Kwota), '0.00')"/>
                                    </td>
                                </tr>
                            </xsl:for-each>
                        </table>

                        <xsl:if test="tns:Fa/tns:Rozliczenie/tns:SumaObciazen">
                            <p class="text-right">
                                <strong>Suma kwot obciążenia: </strong>
                                <xsl:value-of select="format-number(number(tns:Fa/tns:Rozliczenie/tns:SumaObciazen), '0.00')"/>
                            </p>
                        </xsl:if>
                    </xsl:if>
                </div>

                <div class="col-6">
                    <xsl:if test="tns:Fa/tns:Rozliczenie/tns:Odliczenia">
                        <strong>Odliczenia</strong>
                        <table class="table table-sm table-bordered">
                            <tr class="bg-100 font-weight-bold text-nowrap">
                                <td>Powód odliczenia</td>
                                <td>Kwota odliczenia</td>
                            </tr>

                            <xsl:for-each select="tns:Fa/tns:Rozliczenie/tns:Odliczenia">
                                <tr>
                                    <td>
                                        <xsl:value-of select="tns:Powod"/>
                                    </td>

                                    <td class="text-right">
                                        <xsl:value-of select="format-number(number(tns:Kwota), '0.00')"/>
                                    </td>
                                </tr>
                            </xsl:for-each>
                        </table>

                        <xsl:if test="tns:Fa/tns:Rozliczenie/tns:SumaOdliczen">
                            <p class="text-right">
                                <strong>Suma kwot odliczenia: </strong>
                                <xsl:value-of
                                        select="format-number(number(tns:Fa/tns:Rozliczenie/tns:SumaOdliczen), '0.00')"/>
                            </p>
                        </xsl:if>
                    </xsl:if>
                </div>
            </div>

            <h6 class="font-weight-bold text-right" style="color: #434A50;">
                <xsl:if test="tns:Fa/tns:Rozliczenie/tns:DoZaplaty">
                    Do zapłaty:
                    <xsl:value-of select="format-number(number(tns:Fa/tns:Rozliczenie/tns:DoZaplaty), '0.00')"/>
                </xsl:if>

                <xsl:if test="tns:Fa/tns:Rozliczenie/tns:DoRozliczenia">
                    Do rozliczenia:
                    <xsl:value-of select="format-number(number(tns:Fa/tns:Rozliczenie/tns:DoRozliczenia), '0.00')"/>
                </xsl:if>

                <xsl:text> </xsl:text>
                <xsl:value-of select="tns:Fa/tns:KodWaluty"/>
            </h6>
        </xsl:if>
    </xsl:template>

    <xsl:template name="Platnosc">
        <xsl:for-each select="tns:Fa/tns:Platnosc">
            <hr/>
            <h6 class="font-weight-bold">Płatność</h6>
            <strong>Informacja o płatności: </strong>

            <xsl:choose>
                <xsl:when test="tns:Zaplacono = '1'">
                    <xsl:text>Zapłacono</xsl:text>
                </xsl:when>

                <xsl:when test="tns:ZnacznikZaplatyCzesciowej = '1'">
                    <xsl:text>Zapłata częściowa</xsl:text>
                </xsl:when>

                <xsl:otherwise>
                    <xsl:text>Brak zapłaty</xsl:text>
                </xsl:otherwise>
            </xsl:choose>

            <xsl:if test="tns:DataZaplaty">
                <p class="mb-0">
                    <strong>Data zapłaty: </strong>
                    <xsl:value-of select="tns:DataZaplaty"/>
                </p>
            </xsl:if>

            <xsl:if test="tns:ZnacznikZaplatyCzesciowej">
                <p class="mb-0">
                    <strong>Informacja o płatności (kontynuacja): </strong>
                    <xsl:choose>
                        <xsl:when test="tns:ZnacznikZaplatyCzesciowej = '1'">
                            <xsl:text>Zapłacono w części</xsl:text>
                        </xsl:when>

                        <xsl:otherwise>
                            <xsl:text>Zapłacono w całości</xsl:text>
                        </xsl:otherwise>
                    </xsl:choose>
                </p>
            </xsl:if>

            <xsl:if test="tns:FormaPlatnosci|tns:PlatnoscInna">
                <p class="mb-0">
                    <strong>Forma płatności: </strong>
                    <xsl:choose>
                        <xsl:when test="tns:FormaPlatnosci">
                            <xsl:apply-templates select="tns:FormaPlatnosci"/>
                        </xsl:when>

                        <xsl:when test="tns:PlatnoscInna = '1'">
                            <xsl:text>Płatność inna</xsl:text>
                        </xsl:when>
                    </xsl:choose>
                </p>
            </xsl:if>

            <xsl:if test="tns:OpisPlatnosci">
                <p class="mb-0">
                    <strong>Opis płatności: </strong>
                    <xsl:value-of select="tns:OpisPlatnosci"/>
                </p>
            </xsl:if>

            <xsl:if test="tns:LinkDoPlatnosci">
                <p class="mb-0">
                    <strong>Link do płatności bezgotówkowej: </strong>
                    <a href="{tns:LinkDoPlatnosci}">
                        <xsl:value-of select="tns:LinkDoPlatnosci"/>
                    </a>
                </p>
            </xsl:if>

            <xsl:if test="tns:IPKSeF">
                <p class="mb-0">
                    <strong>Identyfikator płatności Krajowego Systemu e-Faktur: </strong>
                    <xsl:value-of select="tns:IPKSeF"/>
                </p>
            </xsl:if>

            <div class="row">
                <div class="col-6">
                    <xsl:if test="tns:ZaplataCzesciowa">
                        <table class="table table-sm table-bordered mt-3">
                            <tr class="bg-100 font-weight-bold">
                                <td>Data zapłaty częściowej</td>
                                <td>Kwota zapłaty częściowej</td>
                                <td>Forma płatności</td>
                            </tr>

                            <xsl:for-each select="tns:ZaplataCzesciowa">
                                <tr>
                                    <td>
                                        <xsl:value-of select="tns:DataZaplatyCzesciowej"/>
                                    </td>

                                    <td class="text-right">
                                        <xsl:value-of
                                                select="format-number(number(tns:KwotaZaplatyCzesciowej), '0.00')"/>
                                    </td>

                                    <td>
                                        <xsl:apply-templates select="tns:FormaPlatnosci"/>
                                    </td>
                                </tr>
                            </xsl:for-each>
                        </table>
                    </xsl:if>
                </div>

                <div class="col-6">
                    <xsl:if test="tns:TerminPlatnosci">
                        <table class="table table-sm table-bordered mt-3">
                            <tr class="bg-100 font-weight-bold text-nowrap">
                                <td>Termin płatności</td>
                                <xsl:if test="tns:TerminPlatnosci/tns:TerminOpis">
                                    <td>Opis płatności</td>
                                </xsl:if>
                            </tr>
                            <xsl:for-each select="tns:TerminPlatnosci">
                                <tr>
                                    <td>
                                        <xsl:value-of select="tns:Termin"/>
                                    </td>

                                    <xsl:if test="tns:TerminOpis">
                                        <td>
                                            <xsl:for-each select="tns:TerminOpis/*">
                                                <xsl:value-of select="."/>
                                                <xsl:if test="position() != last()">
                                                    <xsl:text> </xsl:text>
                                                </xsl:if>
                                            </xsl:for-each>
                                        </td>
                                    </xsl:if>
                                </tr>
                            </xsl:for-each>
                        </table>
                    </xsl:if>
                </div>
            </div>

            <div class="row">
                <div class="col-6">
                    <xsl:if test="tns:RachunekBankowy">
                        <h6 class="font-weight-bold">Numer rachunku bankowego</h6>
                        <table class="table table-sm table-bordered">
                            <xsl:for-each select="tns:RachunekBankowy">
                                <tr>
                                    <td class="bg-100 font-weight-bold text-nowrap">Pełny numer rachunku</td>
                                    <td>
                                        <xsl:value-of select="tns:NrRB"/>
                                    </td>
                                </tr>

                                <xsl:if test="tns:SWIFT">
                                    <tr>
                                        <td class="bg-100 font-weight-bold text-nowrap">Kod SWIFT</td>
                                        <td>
                                            <xsl:value-of select="tns:SWIFT"/>
                                        </td>
                                    </tr>
                                </xsl:if>

                                <tr>
                                    <td class="bg-100 font-weight-bold text-nowrap">Rachunek własny banku</td>
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
                                    <td class="bg-100 font-weight-bold text-nowrap">Nazwa banku</td>
                                    <td>
                                        <xsl:value-of select="tns:NazwaBanku"/>
                                    </td>
                                </tr>

                                <tr>
                                    <td class="bg-100 font-weight-bold text-nowrap">Opis rachunku</td>
                                    <td>
                                        <xsl:value-of select="tns:OpisRachunku"/>
                                    </td>
                                </tr>
                            </xsl:for-each>
                        </table>
                    </xsl:if>
                </div>

                <div class="col-6">
                    <xsl:if test="tns:RachunekBankowyFaktora">
                        <h6 class="font-weight-bold">Numer rachunku bankowego faktora</h6>

                        <table class="table table-sm table-bordered">
                            <xsl:for-each select="tns:RachunekBankowyFaktora">
                                <tr>
                                    <td class="bg-100 font-weight-bold text-nowrap">Pełny numer rachunku</td>
                                    <td>
                                        <xsl:value-of select="tns:NrRB"/>
                                    </td>
                                </tr>

                                <xsl:if test="tns:SWIFT">
                                    <tr>
                                        <td class="bg-100 font-weight-bold text-nowrap">Kod SWIFT</td>
                                        <td>
                                            <xsl:value-of select="tns:SWIFT"/>
                                        </td>
                                    </tr>
                                </xsl:if>

                                <tr>
                                    <td class="bg-100 font-weight-bold text-nowrap">Rachunek własny banku</td>
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
                                    <td class="bg-100 font-weight-bold text-nowrap">Nazwa banku</td>
                                    <td>
                                        <xsl:value-of select="tns:NazwaBanku"/>
                                    </td>
                                </tr>

                                <tr>
                                    <td class="bg-100 font-weight-bold text-nowrap">Opis rachunku</td>
                                    <td>
                                        <xsl:value-of select="tns:OpisRachunku"/>
                                    </td>
                                </tr>
                            </xsl:for-each>
                        </table>
                    </xsl:if>
                </div>
            </div>

            <xsl:if test="tns:Skonto">
                <h6 class="font-weight-bold">Skonto</h6>

                <xsl:if test="tns:Skonto/tns:WarunkiSkonta">
                    <p class="mb-0">
                        <strong>
                            <xsl:text>Warunki skonta: </xsl:text>
                        </strong>
                        <xsl:value-of select="tns:Skonto/tns:WarunkiSkonta"/>
                    </p>
                </xsl:if>

                <xsl:if test="tns:Skonto/tns:WysokoscSkonta">
                    <p class="mb-0">
                        <strong>
                            <xsl:text>Wysokość skonta: </xsl:text>
                        </strong>
                        <xsl:value-of select="tns:Skonto/tns:WysokoscSkonta"/>
                    </p>
                </xsl:if>
            </xsl:if>
        </xsl:for-each>
    </xsl:template>

    <xsl:template name="WarunkiTransakcji">
        <xsl:if test="tns:Fa/tns:WarunkiTransakcji">
            <hr/>
            <h6 class="font-weight-bold">Warunki transakcji</h6>
            <div class="row">
                <div class="col-6">
                    <xsl:if test="tns:Fa/tns:WarunkiTransakcji/tns:Umowy">
                        <xsl:variable name="DataUmowy"
                                      select="boolean(tns:Fa/tns:WarunkiTransakcji/tns:Umowy/tns:DataUmowy)"/>

                        <strong>Umowa</strong>
                        <table class="table table-sm table-bordered">
                            <tr class="bg-100 font-weight-bold text-nowrap">
                                <xsl:if test="$DataUmowy">
                                    <td>Data umowy</td>
                                </xsl:if>
                                <td>Numer umowy</td>
                            </tr>

                            <xsl:for-each select="tns:Fa/tns:WarunkiTransakcji/tns:Umowy">
                                <tr>
                                    <xsl:if test="$DataUmowy">
                                        <td>
                                            <xsl:value-of select="tns:DataUmowy"/>
                                        </td>
                                    </xsl:if>

                                    <td>
                                        <xsl:value-of select="tns:NrUmowy"/>
                                    </td>
                                </tr>
                            </xsl:for-each>
                        </table>
                    </xsl:if>
                </div>

                <div class="col-6">
                    <xsl:if test="tns:Fa/tns:WarunkiTransakcji/tns:Zamowienia">
                        <xsl:variable name="DataZamowienia"
                                      select="boolean(tns:Fa/tns:WarunkiTransakcji/tns:Zamowienia/tns:DataZamowienia)"/>
                        <strong>Zamówienie</strong>

                        <table class="table table-sm table-bordered">
                            <tr class="bg-100 font-weight-bold text-nowrap">
                                <xsl:if test="$DataZamowienia">
                                    <td>Data zamówienia</td>
                                </xsl:if>

                                <td>Numer zamówienia</td>
                            </tr>

                            <xsl:for-each select="tns:Fa/tns:WarunkiTransakcji/tns:Zamowienia">
                                <tr>
                                    <xsl:if test="$DataZamowienia">
                                        <td>
                                            <xsl:value-of select="tns:DataZamowienia"/>
                                        </td>
                                    </xsl:if>

                                    <td>
                                        <xsl:value-of select="tns:NrZamowienia"/>
                                    </td>
                                </tr>
                            </xsl:for-each>
                        </table>
                    </xsl:if>
                </div>
            </div>

            <xsl:if test="tns:Fa/tns:WarunkiTransakcji/tns:WarunkiDostawy">
                <xsl:if test="tns:Fa/tns:WarunkiTransakcji/tns:KursUmowny">
                    <h6 class="font-weight-bold">Waluta umowna i kurs umowny</h6>

                    <p class="mb-0">
                        <strong>
                            <xsl:text>Waluta umowna: </xsl:text>
                        </strong>

                        <xsl:value-of select="tns:Fa/tns:WarunkiTransakcji/tns:WalutaUmowna"/>
                    </p>

                    <p class="mb-0">
                        <strong>
                            <xsl:text>Kurs umowny: </xsl:text>
                        </strong>

                        <xsl:value-of select="tns:Fa/tns:WarunkiTransakcji/tns:KursUmowny"/>
                    </p>
                </xsl:if>

                <p class="mb-0">
                    <strong>
                        <xsl:text>Warunki dostawy towarów: </xsl:text>
                    </strong>

                    <xsl:call-template name="NowaLinia">
                        <xsl:with-param name="text" select="tns:Fa/tns:WarunkiTransakcji/tns:WarunkiDostawy"/>
                    </xsl:call-template>
                </p>
            </xsl:if>
            <hr/>

            <xsl:for-each select="tns:Fa/tns:WarunkiTransakcji/tns:Transport">
                <h6 class="font-weight-bold">Transport
                    <xsl:number/>
                </h6>

                <div class="row">
                    <div class="col-6">
                        <xsl:if test="tns:RodzajTransportu|tns:TransportInny">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Rodzaj transportu: </xsl:text>
                                </strong>

                                <xsl:choose>
                                    <xsl:when test="tns:RodzajTransportu = '1'">
                                        <xsl:text>Transport morski</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:RodzajTransportu = '2'">
                                        <xsl:text>Transport kolejowy</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:RodzajTransportu = '3'">
                                        <xsl:text>Transport drogowy</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:RodzajTransportu = '4'">
                                        <xsl:text>Transport lotniczy</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:RodzajTransportu = '5'">
                                        <xsl:text>Przesyłka pocztowa</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:RodzajTransportu = '7'">
                                        <xsl:text>Stałe instalacje przesyłowe</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:RodzajTransportu = '8'">
                                        <xsl:text>Żegluga śródlądowa</xsl:text>
                                    </xsl:when>

                                    <xsl:otherwise>
                                        <xsl:text>Transport inny</xsl:text>
                                    </xsl:otherwise>
                                </xsl:choose>
                            </p>
                        </xsl:if>

                        <xsl:if test="tns:OpisInnegoTransportu">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Opis innego rodzaju transportu: </xsl:text>
                                </strong>
                                <xsl:value-of select="tns:OpisInnegoTransportu"/>
                            </p>
                        </xsl:if>
                    </div>

                    <div class="col-6">
                        <p class="mb-0">
                            <strong>Dane transportu</strong>
                        </p>

                        <xsl:if test="tns:NrZleceniaTransportu">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Numer zlecenia transportu: </xsl:text>
                                </strong>

                                <xsl:value-of select="tns:NrZleceniaTransportu"/>
                            </p>
                        </xsl:if>

                        <xsl:if test="tns:OpisLadunku">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Opis ładunku: </xsl:text>
                                </strong>

                                <xsl:choose>
                                    <xsl:when test="tns:OpisLadunku = '1'">
                                        <xsl:text>Bańka</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '2'">
                                        <xsl:text>Beczka</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '3'">
                                        <xsl:text>Butla</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '4'">
                                        <xsl:text>Karton</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '5'">
                                        <xsl:text>Kanister</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '6'">
                                        <xsl:text>Klatka</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '7'">
                                        <xsl:text>Kontener</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '8'">
                                        <xsl:text>Kosz/koszyk</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '9'">
                                        <xsl:text>Łubianka</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '10'">
                                        <xsl:text>Opakowanie zbiorcze</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '11'">
                                        <xsl:text>Paczka</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '12'">
                                        <xsl:text>Pakiet</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '13'">
                                        <xsl:text>Paleta</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '14'">
                                        <xsl:text>Pojemnik</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '15'">
                                        <xsl:text>Pojemnik do ładunków masowych stałych</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '16'">
                                        <xsl:text>Pojemnik do ładunków masowych w postaci płynnej</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '17'">
                                        <xsl:text>Pudełko</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '18'">
                                        <xsl:text>Puszka</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '19'">
                                        <xsl:text>Skrzynia</xsl:text>
                                    </xsl:when>

                                    <xsl:when test="tns:OpisLadunku = '20'">
                                        <xsl:text>Worek</xsl:text>
                                    </xsl:when>
                                </xsl:choose>
                            </p>
                        </xsl:if>

                        <xsl:if test="tns:JednostkaOpakowania">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Jednostka opakowania: </xsl:text>
                                </strong>

                                <xsl:value-of select="tns:JednostkaOpakowania"/>
                            </p>
                        </xsl:if>

                        <xsl:if test="tns:DataGodzRozpTransportu">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Data i godzina rozpoczęcia transportu: </xsl:text>
                                </strong>

                                <xsl:value-of select="tns:DataGodzRozpTransportu"/>
                            </p>
                        </xsl:if>

                        <xsl:if test="tns:DataGodzZakTransportu">
                            <p class="mb-0">
                                <strong>
                                    <xsl:text>Data i godzina zakończenia transportu: </xsl:text>
                                </strong>

                                <xsl:value-of select="tns:DataGodzZakTransportu"/>
                            </p>
                        </xsl:if>
                    </div>
                </div>

                <xsl:if test="tns:Przewoznik">
                    <h6 class="font-weight-bold mt-3">Przewoźnik</h6>
                    <div class="row">
                        <div class="col-6">
                            <xsl:apply-templates select="tns:Przewoznik"/>
                        </div>

                        <div class="col-6">
                            <xsl:if test="tns:Przewoznik/tns:AdresPrzewoznika">
                                <p class="mb-0">
                                    <strong>Adres przewoźnika</strong>
                                </p>

                                <xsl:apply-templates select="tns:Przewoznik/tns:AdresPrzewoznika"/>
                            </xsl:if>
                        </div>
                    </div>
                </xsl:if>

                <xsl:if test="tns:WysylkaZ|tns:WysylkaPrzez|tns:WysylkaDo">
                    <h6 class="font-weight-bold mt-3">Wysyłka</h6>
                    <div class="row">
                        <div class="col-6">
                            <xsl:if test="tns:WysylkaZ">
                                <p class="mb-0">
                                    <strong>Adres miejsca wysyłki</strong>
                                </p>

                                <xsl:apply-templates select="tns:WysylkaZ"/>
                            </xsl:if>

                            <xsl:if test="tns:WysylkaPrzez">
                                <p class="mt-3 mb-0">
                                    <strong>Adres pośredni wysyłki</strong>
                                </p>

                                <xsl:apply-templates select="tns:WysylkaPrzez"/>
                            </xsl:if>
                        </div>

                        <div class="col-6">
                            <xsl:if test="tns:WysylkaDo">
                                <p class="mb-0">
                                    <strong>Adres miejsca docelowego, do którego został zlecony transport</strong>
                                </p>

                                <xsl:apply-templates select="tns:WysylkaDo"/>
                            </xsl:if>
                        </div>
                    </div>
                </xsl:if>
            </xsl:for-each>
        </xsl:if>
    </xsl:template>

    <xsl:template name="WZ">
        <xsl:if test="tns:Fa/tns:WZ">
            <hr/>
            <h6 class="font-weight-bold">Numery dokumentów magazynowych WZ</h6>
            <table class="table table-sm table-bordered w-50">
                <tr>
                    <td class="bg-100 font-weight-bold text-nowrap">Numer WZ</td>
                </tr>

                <xsl:for-each select="tns:Fa/tns:WZ">
                    <tr>
                        <td>
                            <xsl:value-of select="."/>
                        </td>
                    </tr>
                </xsl:for-each>
            </table>
        </xsl:if>
    </xsl:template>

    <xsl:template name="Stopka">
        <xsl:if test="tns:Stopka/tns:Rejestry|tns:Stopka/tns:Informacje/tns:StopkaFaktury">
            <hr/>
            <xsl:if test="tns:Stopka/tns:Rejestry">
                <xsl:variable name="PelnaNazwa" select="boolean(tns:Stopka/tns:Rejestry/tns:PelnaNazwa)"/>
                <xsl:variable name="Krs" select="boolean(tns:Stopka/tns:Rejestry/tns:KRS)"/>
                <xsl:variable name="Regon" select="boolean(tns:Stopka/tns:Rejestry/tns:REGON)"/>
                <xsl:variable name="Bdo" select="boolean(tns:Stopka/tns:Rejestry/tns:BDO)"/>

                <h6 class="font-weight-bold">Rejestry</h6>
                <table class="table table-sm table-bordered">
                    <tr class="bg-100 font-weight-bold text-nowrap">
                        <xsl:if test="$PelnaNazwa">
                            <td>Pełna nazwa</td>
                        </xsl:if>

                        <xsl:if test="$Krs">
                            <td>KRS</td>
                        </xsl:if>

                        <xsl:if test="$Regon">
                            <td>Regon</td>
                        </xsl:if>

                        <xsl:if test="$Bdo">
                            <td>BDO</td>
                        </xsl:if>
                    </tr>

                    <xsl:for-each select="tns:Stopka/tns:Rejestry">
                        <tr>
                            <xsl:if test="$PelnaNazwa">
                                <td>
                                    <xsl:value-of select="tns:PelnaNazwa"/>
                                </td>
                            </xsl:if>

                            <xsl:if test="$Krs">
                                <td>
                                    <xsl:value-of select="tns:KRS"/>
                                </td>
                            </xsl:if>

                            <xsl:if test="$Regon">
                                <td>
                                    <xsl:value-of select="tns:REGON"/>
                                </td>
                            </xsl:if>

                            <xsl:if test="$Bdo">
                                <td>
                                    <xsl:value-of select="tns:BDO"/>
                                </td>
                            </xsl:if>
                        </tr>
                    </xsl:for-each>
                </table>
            </xsl:if>

            <xsl:if test="tns:Stopka/tns:Informacje/tns:StopkaFaktury">
                <h6 class="font-weight-bold">Pozostałe informacje</h6>
                <table class="table table-sm table-bordered">
                    <tr class="bg-100 font-weight-bold text-nowrap">
                        <td>Stopka faktury</td>
                    </tr>

                    <xsl:for-each select="tns:Stopka/tns:Informacje">
                        <tr>
                            <td>
                                <xsl:value-of select="tns:StopkaFaktury"/>
                            </td>
                        </tr>
                    </xsl:for-each>
                </table>
            </xsl:if>
        </xsl:if>
    </xsl:template>

    <xsl:template match="tns:Adres|tns:AdresKoresp|tns:AdresPrzewoznika|tns:WysylkaZ|tns:WysylkaPrzez|tns:WysylkaDo">
        <p class="m-0">
            <xsl:call-template name="NowaLinia">
                <xsl:with-param name="text" select="tns:AdresL1"/>
            </xsl:call-template>
        </p>

        <xsl:if test="tns:AdresL2">
            <p class="m-0">
                <xsl:call-template name="NowaLinia">
                    <xsl:with-param name="text" select="tns:AdresL2"/>
                </xsl:call-template>
            </p>
        </xsl:if>

        <p class="m-0">
            <xsl:apply-templates select="tns:KodKraju"/>
        </p>

        <xsl:if test="tns:GLN">
            <p class="mb-0">
                <strong>
                    <xsl:text>GLN: </xsl:text>
                </strong>

                <xsl:value-of select="tns:GLN"/>
            </p>
        </xsl:if>
    </xsl:template>

    <xsl:template match="tns:Podmiot1|tns:Podmiot2|tns:Podmiot3|tns:Przewoznik">
        <xsl:if test="tns:NrEORI">
            <p class="mb-0">
                <strong>
                    <xsl:text>Numer EORI: </xsl:text>
                </strong>

                <xsl:value-of select="tns:NrEORI"/>
            </p>
        </xsl:if>

        <xsl:if test="tns:PrefiksPodatnika">
            <p class="mb-0">
                <strong>
                    <xsl:text>Prefiks VAT: </xsl:text>
                </strong>

                <xsl:value-of select="tns:PrefiksPodatnika"/>
            </p>
        </xsl:if>

        <xsl:if test="tns:DaneIdentyfikacyjne/tns:NIP">
            <p class="mb-0">
                <strong>
                    <xsl:text>NIP: </xsl:text>
                </strong>

                <xsl:value-of select="tns:DaneIdentyfikacyjne/tns:NIP"/>
            </p>
        </xsl:if>

        <xsl:if test="tns:DaneIdentyfikacyjne/tns:NrVatUE">
            <p class="mb-0">
                <strong>
                    <xsl:text>Numer VAT-UE: </xsl:text>
                </strong>

                <xsl:value-of select="tns:DaneIdentyfikacyjne/tns:KodUE"/>
                <xsl:value-of select="tns:DaneIdentyfikacyjne/tns:NrVatUE"/>
            </p>
        </xsl:if>

        <xsl:if test="tns:DaneIdentyfikacyjne/tns:NrID">
            <p class="mb-0">
                <strong>
                    <xsl:text>Identyfikator podatkowy inny: </xsl:text>
                </strong>

                <xsl:value-of select="tns:DaneIdentyfikacyjne/tns:KodKraju"/>
                <xsl:value-of select="tns:DaneIdentyfikacyjne/tns:NrID"/>
            </p>
        </xsl:if>

        <xsl:if test="tns:DaneIdentyfikacyjne/tns:BrakID = '1'">
            <p class="mb-0">
                <strong>
                    <xsl:text>Brak identyfikatora</xsl:text>
                </strong>
            </p>
        </xsl:if>

        <p class="mb-0">
            <strong>
                <xsl:text>Nazwa: </xsl:text>
            </strong>

            <xsl:call-template name="NowaLinia">
                <xsl:with-param name="text" select="tns:DaneIdentyfikacyjne/tns:Nazwa"/>
            </xsl:call-template>
        </p>

        <xsl:if test="tns:Rola">
            <p class="mb-0">
                <strong>
                    <xsl:text>Rola: </xsl:text>
                </strong>

                <xsl:choose>
                    <xsl:when test="tns:Rola = '1'">
                        <xsl:text>Faktor - w przypadku gdy na fakturze występują dane faktora</xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Rola = '2'">
                        <xsl:text>
                            Odbiorca - w przypadku gdy na fakturze występują dane jednostek wewnętrznych, oddziałów,
                            wyodrębnionych w ramach nabywcy, które same nie stanowią nabywcy w rozumieniu ustawy
                        </xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Rola = '3'">
                        <xsl:text>
                            Podmiot pierwotny - w przypadku gdy na fakturze występują dane podmiotu będącego w stosunku
                            do podatnika podmiotem przejętym lub przekształconym, który dokonywał dostawy lub świadczył
                            usługę. Z wyłączeniem przypadków, o których mowa w art. 106j ust.2 pkt 3 ustawy, gdy dane
                            te wykazywane są w części Podmiot1K
                        </xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Rola = '4'">
                        <xsl:text>
                            Dodatkowy nabywca - w przypadku gdy na fakturze występują dane kolejnych
                            (innych niż wymieniony w części Podmiot2) nabywców
                        </xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Rola = '5'">
                        <xsl:text>
                            Wystawca faktury - w przypadku gdy na fakturze występują dane podmiotu wystawiającego
                            fakturę w imieniu podatnika
                        </xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Rola = '6'">
                        <xsl:text>
                            Dokonujący płatności - w przypadku gdy na fakturze występują dane podmiotu regulującego
                            zobowiązanie w miejsce nabywcy
                        </xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Rola = '7'">
                        <xsl:text>Jednostka samorządu terytorialnego – wystawca</xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Rola = '8'">
                        <xsl:text>Jednostka samorządu terytorialnego - odbiorca</xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Rola = '9'">
                        <xsl:text>Członek grupy VAT – wystawca</xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Rola = '10'">
                        <xsl:text>Członek grupy VAT – odbiorca</xsl:text>
                    </xsl:when>

                    <xsl:when test="tns:Rola = '11'">
                        <xsl:text>Pracownik</xsl:text>
                    </xsl:when>
                </xsl:choose>
            </p>
        </xsl:if>
    </xsl:template>

    <xsl:template match="tns:DaneKontaktowe">
        <xsl:for-each select=".">
            <xsl:if test="tns:Email">
                <p class="mb-0">
                    <strong>
                        <xsl:text>E-mail: </xsl:text>
                    </strong>

                    <xsl:value-of select="tns:Email"/>
                </p>
            </xsl:if>

            <xsl:if test="tns:Telefon">
                <p class="mb-0">
                    <strong>
                        <xsl:text>Tel.: </xsl:text>
                    </strong>

                    <xsl:value-of select="tns:Telefon"/>
                </p>
            </xsl:if>
        </xsl:for-each>
    </xsl:template>

    <xsl:template match="tns:FormaPlatnosci">
        <xsl:choose>
            <xsl:when test=". = '1'">
                <xsl:text>Gotówka</xsl:text>
            </xsl:when>

            <xsl:when test=". = '2'">
                <xsl:text>Karta</xsl:text>
            </xsl:when>

            <xsl:when test=". = '3'">
                <xsl:text>Bon</xsl:text>
            </xsl:when>

            <xsl:when test=". = '4'">
                <xsl:text>Czek</xsl:text>
            </xsl:when>

            <xsl:when test=". = '5'">
                <xsl:text>Kredyt</xsl:text>
            </xsl:when>

            <xsl:when test=". = '6'">
                <xsl:text>Przelew</xsl:text>
            </xsl:when>

            <xsl:when test=". = '7'">
                <xsl:text>Mobilna</xsl:text>
            </xsl:when>
        </xsl:choose>
    </xsl:template>

    <xsl:template match="tns:KodKraju">
        <xsl:variable name="kod" select="normalize-space(.)"/>
        <xsl:variable name="nazwa"
                      select="document($schema-krajow)//xsd:simpleType[@name='TKodKraju']//xsd:enumeration[@value = $kod]/xsd:annotation/xsd:documentation"/>

        <xsl:choose>
            <xsl:when test="string($nazwa)">
                <xsl:value-of select="$nazwa"/>
            </xsl:when>

            <xsl:otherwise>
                <xsl:value-of select="$kod"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <xsl:template name="NowaLinia">
        <xsl:param name="text" />
        <xsl:choose>
            <xsl:when test="contains($text,'&#xa;')">
                <xsl:value-of select="substring-before($text, '&#xa;')"  disable-output-escaping="yes"/>
                <br />
                <xsl:call-template name="NowaLinia">
                    <xsl:with-param name="text" select="substring-after($text,'&#xa;')"/>
                </xsl:call-template>
            </xsl:when>

            <xsl:otherwise>
                <xsl:value-of select="$text" disable-output-escaping="yes"/>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
</xsl:stylesheet>
