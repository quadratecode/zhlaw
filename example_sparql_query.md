PREFIX cogni: <http://cogni.internal.system/model#>
PREFIX zone: <http://cogni.zone/internal/properties/>
PREFIX legiconso: <http://data.cogni.zone/internal/legiconso#>
PREFIX mapping: <http://data.cogni.zone/model/legiconso/jolux_mapping#>
PREFIX eli: <http://data.europa.eu/eli/ontology#>
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?property ?value
WHERE {
  # Find the document based on its taxonomy entry’s srNotation…
  ?doc jolux:classifiedByTaxonomyEntry ?entry .
  ?entry skos:notation ?srNotation .
  FILTER(str(?srNotation) = "YOUR_SR_NOTATION")
  
  # …and filter by the document’s dateEntryInForce
  ?doc jolux:dateEntryInForce ?docDateEntryInForce .
  FILTER(str(?docDateEntryInForce) = "YOUR_DATE_ENTRY_IN_FORCE")
  
  # Return all properties of the document that are in the allowed list
  ?doc ?property ?value .
  FILTER(
         ?property = <http://cogni.internal.system/model#aper> ||
         ?property = <http://cogni.internal.system/model#botschaftDate> ||
         ?property = <http://cogni.internal.system/model#firstPublicationDate> ||
         ?property = <http://cogni.internal.system/model#historicalId> ||
         ?property = <http://cogni.internal.system/model#impactDate> ||
         ?property = <http://cogni.internal.system/model#migrationDataGroup> ||
         ?property = <http://cogni.internal.system/model#migrationDateTime_Casemates> ||
         ?property = <http://cogni.internal.system/model#mutationReferenz> ||
         ?property = <http://cogni.internal.system/model#mutationRtArt> ||
         ?property = <http://cogni.internal.system/model#originalId> ||
         ?property = <http://cogni.internal.system/model#repealDecisionDate_datum> ||
         ?property = <http://cogni.internal.system/model#skipIndex> ||
         ?property = <http://cogni.internal.system/model#sourceDatabaseDumpDate_Casemates> ||
         ?property = <http://cogni.internal.system/model#srInBearbeitung> ||
         ?property = <http://cogni.internal.system/model#terminDate> ||
         ?property = <http://cogni.zone/internal/properties/id> ||
         ?property = <http://cogni.zone/internal/properties/wasNotFoundAct> ||
         ?property = <http://data.cogni.zone/internal/legiconso#consolidated> ||
         ?property = <http://data.cogni.zone/internal/legiconso#impactsToUpdate> ||
         ?property = <http://data.cogni.zone/model/legiconso/jolux_mapping#isDirectUpdated> ||
         ?property = <http://data.cogni.zone/model/legiconso/jolux_mapping#toBeMapped_impactToLegalResource> ||
         ?property = <http://data.europa.eu/eli/ontology#originalName> ||
         ?property = <http://data.europa.eu/eli/ontology#specificPropertyOf> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#actIsFollowingActForCompendium> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#actToTakeIntoAccount> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#activeInVernehm> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#address> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#alignmentComment> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#annexIsExemplifiedBy> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#approbationAct> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#basicAct> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#basicActLabel> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#bilateral> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#binderNumber> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#citationFromLegalResource> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#citationFromReference> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#citationToLegalResource> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#citationToLegalTaxonomy> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#citationToRs> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#classifiedByTaxonomyEntry> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#comment> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#compendiumIntegratesAct> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#consolidated> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#consultationHasModification> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#consultationStageDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#consultationStatus> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#dateApplicability> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#dateApplicabilityForOurCountry> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#dateDocument> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#dateEndApplicability> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#dateEndApplicabilityForOurCountry> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#dateEntryInForce> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#dateNoLongerInForce> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#decisionDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#depositary> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#descriptionFrom> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#draftHasLegislativeTask> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#draftHasStage> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#draftHasTask> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#draftId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#draftLegislationApprovalDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#draftLegislationApprovalPublishedIn> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#draftLegislationInitialInformationPublishedIn> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#draftProcessDocumentType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#editionNumber> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#editionType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#email> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#entryIntoForceDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#entryIntoForceFor> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#euConventionDomain> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#eventDescription> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#eventEndDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#eventId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#eventOrder> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#eventStartDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#eventTitle> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#eventUnderResponsibilityOf> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#factor> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#familyName> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#federalCouncilEventId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#firstEntryIntoForceDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#foreseenEventEndDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#foreseenEventStartDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#foreseenImpactToLegalResource> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#format> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#givenName> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#hasResultingLegalResource> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#hasSubTask> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#historicalId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#historicalImpact> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#historicalLegalId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#historicalPublicationFileId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#historicalTypeDocument> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#impactConsolidatedBy> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#impactConsolidatedByExpression> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#impactFromLegalResource> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#impactFromLegalResourceComment> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#impactFromLegalResourceLabel> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#impactToExpression> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#impactToLegalResource> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#impactToLegalResourceComment> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#inForceStatus> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#incorporates> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#informationSource> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#institutionInChargeOfTheEvent> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#institutionInChargeOfTheEventLevel2> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#institutionInChargeOfTheEventLevel3> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#isAnnexOfWork> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#isEmbodiedBy> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#isExemplifiedBy> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#isExemplifiedByPrivate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#isFollowingAct> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#isIncorporatedBy> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#isMemberOf> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#isOpinionOf> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#isPartOf> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#isRealizedBy> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#language> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalAnalysisHasLegalResourceImpact> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalAnalysisOfLegalResource> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalBase> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalInstitutionAllowedToPublish> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalInstitutionForLegalSupport> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalInstitutionForOpinion> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalInstitutionForTechnicalSupport> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceFamilyType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceGenre> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceHasImpact> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceImpactHasDateEntryInForce> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceImpactHasType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceImpactIsDirect> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceIsPartOfMemorialLabel> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourcePublicationCompleteness> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceSubdivisionDetailId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceSubdivisionDetailType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceSubdivisionHasSubdivisionIdentificationDetail> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceSubdivisionIsPartOf> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceSubdivisionType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legalResourceWasPublishedByPublicationProcess> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legislativeTaskHasResultingLegalResource> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legislativeTaskHasResultingLegalResourceLabel> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#legislativeTaskType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#manifestationByDefault> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#manifestationNotToBePrinted> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#membershipHasMember> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#memorialName> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#memorialNumber> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#memorialPage> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#memorialPageTo> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#memorialYear> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#migrationDraftStageDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#migrationDraftStageType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#modifiedBy> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#modifies> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#nonAnonymousWorkToRemoveDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#note> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#notificationDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#notificationEntryIntoForceDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#notificationFrom> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#notificationType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#numberOfCopiesRemaining> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#numberOfPages> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#observation> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#opinionHasDraftRelatedDocument> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#opinionIsAboutDraftDocument> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#order> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#outputDocumentOfPublicationTask> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#parliamentDraftId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#partyConditionAccessionType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#partyConditionHasRatificationRestriction> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#partyConditionObjection> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#partyConditionOfParty> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#partyConditionReservationAndDeclaration> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#partyOrganisationOfTreaty> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#processType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#producedIn> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#provisionalApplicationDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#publicationDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#publicationDateGreg> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#publicationProcessForConsolidationAbstract> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#publicationProcessHasPublicationTask> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#publicationProcessHasPublicationTaskRelatedToExpression> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#publicationProcessId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#publicationProcessStatus> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#publicationProcessTakesIntoAccountLegalAnalysis> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#publicationTaskRelatedToExpressionStatus> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#publisher> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#ratificationRestrictionDescription> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#ratificationRestrictionId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#rectifies> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#relatedProjectTask> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#relatedProjectType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#relatedResourceFamily> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#responsibilityOf> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#rightsHolder> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#seeAlsoSource> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#seeAlsoTarget> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#sequenceInTheYearOfPublication> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#shortTitle> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#streetAddress> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#subdivisionIdentificationDetailOrder> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#subdivisionType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#taskTriggersPublicationProcess> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#telephone> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#temporaryParliamentDraftId> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#title> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#titleAlternative> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#titleShort> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#titleTreaty> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyDateNoLongerInForceForOurCountry> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyExpirationDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyHasRatificationRestriction> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyInForceDateForOurCountry> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyLegalResourceForOtherParty> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyNotificationPublishedIn> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyPartyCountry> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyPartyOrganisation> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyPartyRatificationDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyProcessHasPartyCondition> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyProcessHasResultingTreatyDocument> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyProcessHasTask> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyRatificationParty> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatySignatureDate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatySignaturePlace> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatySubject> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyType> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#treatyUnderUmbrellaOf> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#typeDocument> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#uploadDateCasemates> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#uploadDateLegiconso> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#userFormat> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#volumePage> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#volumePageTo> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#volumeYear> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#wasExemplifiedBy> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#wasExemplifiedByPrivate> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#website> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#workHasAnnex> ||
         ?property = <http://data.legilux.public.lu/resource/ontology/jolux#workIdDocument> ||
         ?property = <http://publications.europa.eu/ontology/euvoc#endDate> ||
         ?property = <http://publications.europa.eu/ontology/euvoc#startDate> ||
         ?property = <http://publications.europa.eu/ontology/euvoc#status> ||
         ?property = <http://purl.org/dc/elements/1.1/subject> ||
         ?property = <http://purl.org/dc/terms/contributor> ||
         ?property = <http://purl.org/dc/terms/created> ||
         ?property = <http://purl.org/dc/terms/creator> ||
         ?property = <http://purl.org/dc/terms/description> ||
         ?property = <http://purl.org/dc/terms/extent> ||
         ?property = <http://purl.org/dc/terms/identifier> ||
         ?property = <http://purl.org/dc/terms/isRequiredBy> ||
         ?property = <http://purl.org/dc/terms/license> ||
         ?property = <http://purl.org/dc/terms/modified> ||
         ?property = <http://purl.org/dc/terms/publisher> ||
         ?property = <http://purl.org/dc/terms/replaces> ||
         ?property = <http://purl.org/dc/terms/rights> ||
         ?property = <http://purl.org/dc/terms/title> ||
         ?property = <http://purl.org/dc/terms/type> ||
         ?property = <http://purl.org/umu/uneskos#hasMicroThesaurus> ||
         ?property = <http://purl.org/vocab/vann/preferredNamespacePrefix> ||
         ?property = <http://www.openlinksw.com/schemas/DAV#ownerUser> ||
         ?property = <http://www.openlinksw.com/schemas/virtrdf#graph-crud-endpoint> ||
         ?property = <http://www.w3.org/1999/02/22-rdf-syntax-ns#first> ||
         ?property = <http://www.w3.org/1999/02/22-rdf-syntax-ns#rest> ||
         ?property = <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> ||
         ?property = <http://www.w3.org/2000/01/rdf-schema#comment> ||
         ?property = <http://www.w3.org/2000/01/rdf-schema#domain> ||
         ?property = <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> ||
         ?property = <http://www.w3.org/2000/01/rdf-schema#label> ||
         ?property = <http://www.w3.org/2000/01/rdf-schema#range> ||
         ?property = <http://www.w3.org/2000/01/rdf-schema#seeAlso> ||
         ?property = <http://www.w3.org/2000/01/rdf-schema#subClassOf> ||
         ?property = <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> ||
         ?property = <http://www.w3.org/2002/07/owl#allValuesFrom> ||
         ?property = <http://www.w3.org/2002/07/owl#annotatedProperty> ||
         ?property = <http://www.w3.org/2002/07/owl#annotatedSource> ||
         ?property = <http://www.w3.org/2002/07/owl#annotatedTarget> ||
         ?property = <http://www.w3.org/2002/07/owl#cardinality> ||
         ?property = <http://www.w3.org/2002/07/owl#complementOf> ||
         ?property = <http://www.w3.org/2002/07/owl#deprecated> ||
         ?property = <http://www.w3.org/2002/07/owl#disjointWith> ||
         ?property = <http://www.w3.org/2002/07/owl#equivalentClass> ||
         ?property = <http://www.w3.org/2002/07/owl#equivalentProperty> ||
         ?property = <http://www.w3.org/2002/07/owl#hasValue> ||
         ?property = <http://www.w3.org/2002/07/owl#imports> ||
         ?property = <http://www.w3.org/2002/07/owl#intersectionOf> ||
         ?property = <http://www.w3.org/2002/07/owl#inverseOf> ||
         ?property = <http://www.w3.org/2002/07/owl#maxCardinality> ||
         ?property = <http://www.w3.org/2002/07/owl#maxQualifiedCardinality> ||
         ?property = <http://www.w3.org/2002/07/owl#minCardinality> ||
         ?property = <http://www.w3.org/2002/07/owl#minQualifiedCardinality> ||
         ?property = <http://www.w3.org/2002/07/owl#onClass> ||
         ?property = <http://www.w3.org/2002/07/owl#onDataRange> ||
         ?property = <http://www.w3.org/2002/07/owl#onProperty> ||
         ?property = <http://www.w3.org/2002/07/owl#priorVersion> ||
         ?property = <http://www.w3.org/2002/07/owl#propertyChainAxiom> ||
         ?property = <http://www.w3.org/2002/07/owl#qualifiedCardinality> ||
         ?property = <http://www.w3.org/2002/07/owl#sameAs> ||
         ?property = <http://www.w3.org/2002/07/owl#someValuesFrom> ||
         ?property = <http://www.w3.org/2002/07/owl#unionOf> ||
         ?property = <http://www.w3.org/2002/07/owl#versionIRI> ||
         ?property = <http://www.w3.org/2002/07/owl#versionInfo> ||
         ?property = <http://www.w3.org/2003/06/sw-vocab-status/ns#term_status> ||
         ?property = <http://www.w3.org/2004/02/skos/core#altLabel> ||
         ?property = <http://www.w3.org/2004/02/skos/core#broader> ||
         ?property = <http://www.w3.org/2004/02/skos/core#broaderTransitive> ||
         ?property = <http://www.w3.org/2004/02/skos/core#closeMatch> ||
         ?property = <http://www.w3.org/2004/02/skos/core#definition> ||
         ?property = <http://www.w3.org/2004/02/skos/core#editorialNote> ||
         ?property = <http://www.w3.org/2004/02/skos/core#exactMatch> ||
         ?property = <http://www.w3.org/2004/02/skos/core#example> ||
         ?property = <http://www.w3.org/2004/02/skos/core#hasTopConcept> ||
         ?property = <http://www.w3.org/2004/02/skos/core#historyNote> ||
         ?property = <http://www.w3.org/2004/02/skos/core#inScheme> ||
         ?property = <http://www.w3.org/2004/02/skos/core#member> ||
         ?property = <http://www.w3.org/2004/02/skos/core#narrower> ||
         ?property = <http://www.w3.org/2004/02/skos/core#notation> ||
         ?property = <http://www.w3.org/2004/02/skos/core#prefLabel> ||
         ?property = <http://www.w3.org/2004/02/skos/core#related> ||
         ?property = <http://www.w3.org/2004/02/skos/core#relatedMatch> ||
         ?property = <http://www.w3.org/2004/02/skos/core#scopeNote> ||
         ?property = <http://www.w3.org/2004/02/skos/core#topConceptOf> ||
         ?property = <http://www.w3.org/ns/prov#category> ||
         ?property = <http://www.w3.org/ns/prov#component> ||
         ?property = <http://www.w3.org/ns/prov#constraints> ||
         ?property = <http://www.w3.org/ns/prov#definition> ||
         ?property = <http://www.w3.org/ns/prov#dm> ||
         ?property = <http://www.w3.org/ns/prov#editorialNote> ||
         ?property = <http://www.w3.org/ns/prov#editorsDefinition> ||
         ?property = <http://www.w3.org/ns/prov#inverse> ||
         ?property = <http://www.w3.org/ns/prov#n> ||
         ?property = <http://www.w3.org/ns/prov#qualifiedForm> ||
         ?property = <http://www.w3.org/ns/prov#sharesDefinitionWith> ||
         ?property = <http://www.w3.org/ns/prov#unqualifiedForm> ||
         ?property = <http://www.w3.org/ns/sparql-service-description#endpoint> ||
         ?property = <http://www.w3.org/ns/sparql-service-description#extensionAggregate> ||
         ?property = <http://www.w3.org/ns/sparql-service-description#extensionFunction> ||
         ?property = <http://www.w3.org/ns/sparql-service-description#feature> ||
         ?property = <http://www.w3.org/ns/sparql-service-description#inputFormat> ||
         ?property = <http://www.w3.org/ns/sparql-service-description#languageExtension> ||
         ?property = <http://www.w3.org/ns/sparql-service-description#propertyFeature> ||
         ?property = <http://www.w3.org/ns/sparql-service-description#resultFormat> ||
         ?property = <http://www.w3.org/ns/sparql-service-description#supportedLanguage> ||
         ?property = <http://www.w3.org/ns/sparql-service-description#url> ||
         ?property = <https://domi.com/test> ||
         ?property = <https://fedlex.data.admin.ch/vocabulary/model#legal-taxonomy-concept-type>
  )
}


PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd:   <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT 
  ?title 
  ?abbreviation 
  ?titleAlternative 
  (str(?dateDocumentNode) AS ?dateDocument) 
  (str(?dateEntryInForceNode) AS ?dateEntryInForce) 
  (str(?publicationDateNode) AS ?publicationDate) 
  (str(?languageNotation) AS ?languageTag) 
  (str(?dateApplicabilityNode) AS ?dateApplicability) 
  (str(?fileFormatNode) AS ?fileFormat)
  (str(?aufhebungsdatum) AS ?aufhebungsdatum)
  ?fileURL
{
  VALUES (?srString)        { ("101") }
  VALUES (?validDateString) { ("2024-03-03") }
  
  ?consoAbstract a jolux:ConsolidationAbstract .
  ?consoAbstract jolux:classifiedByTaxonomyEntry/skos:notation ?rsNotation . 
  FILTER(str(?rsNotation) = ?srString)
  
  # Retrieve dateDocument, dateEntryInForce, and publicationDate from the abstract
  ?consoAbstract jolux:dateDocument ?dateDocumentNode . 
  OPTIONAL { ?consoAbstract jolux:dateEntryInForce ?dateEntryInForceNode . }
  OPTIONAL { ?consoAbstract jolux:publicationDate ?publicationDateNode . }
  
  ?consoAbstract jolux:isRealizedBy ?consoAbstractExpression .
  ?consoAbstractExpression jolux:language ?languageConcept .
  ?consoAbstractExpression jolux:title ?title .
  OPTIONAL { ?consoAbstractExpression jolux:titleShort ?abbreviation . }
  OPTIONAL { ?consoAbstractExpression jolux:titleAlternative ?titleAlternative . }
  OPTIONAL { ?consoAbstract jolux:dateEndApplicability ?ccEndDate . }
  FILTER(!BOUND(?ccEndDate) || xsd:date(?ccEndDate) >= xsd:date(?validDateString))
  OPTIONAL { ?consoAbstract jolux:dateNoLongerInForce ?ccEndForce . }
  FILTER(!BOUND(?ccEndForce) || xsd:date(?ccEndForce) > xsd:date(?validDateString))
  
  ?conso a jolux:Consolidation .
  ?conso jolux:isMemberOf ?consoAbstract .
  ?conso jolux:dateApplicability ?dateApplicabilityNode .
  OPTIONAL { ?conso jolux:dateEndApplicability ?endDate . }
  FILTER(xsd:date(?dateApplicabilityNode) <= xsd:date(?validDateString))
  FILTER(!BOUND(?endDate) || xsd:date(?endDate) >= xsd:date(?validDateString))
  
  ?conso jolux:isRealizedBy ?consoExpression . 
  ?consoExpression jolux:isEmbodiedBy ?manifestation .
  ?consoExpression jolux:language ?languageConcept .
  ?manifestation jolux:isExemplifiedBy ?fileURL .
  ?manifestation jolux:userFormat/skos:notation ?fileFormatNode . 
  FILTER(datatype(?fileFormatNode) = <https://fedlex.data.admin.ch/vocabulary/notation-type/uri-suffix>)
  
  ?languageConcept skos:notation ?languageNotation .
  FILTER(datatype(?languageNotation) = <http://publications.europa.eu/ontology/euvoc#XML_LNG>)
  
  # Only show results where fileFormat is "html"
  FILTER(str(?fileFormatNode) = "html")
  
  # Only show results where language is "de"
  FILTER(str(?languageNotation) = "de")
}
ORDER BY ?languageTag ?fileFormat


PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd:   <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT 
  (str(?srNotation) AS ?rsNr) 
  (str(?dateApplicabilityNode) AS ?dateApplicability) 
  ?title 
  ?abbreviation 
  ?titleAlternative 
  (str(?dateDocumentNode) AS ?dateDocument) 
  (str(?dateEntryInForceNode) AS ?dateEntryInForce) 
  (str(?publicationDateNode) AS ?publicationDate) 
  (str(?languageNotation) AS ?languageTag) 
  (str(?fileFormatNode) AS ?fileFormat)
  (str(?aufhebungsdatum) AS ?aufhebungsdatum)
  ?fileURL
WHERE {
  # Use the current date for all validity comparisons
  BIND(now() AS ?currentDate)
  # Use German as the language filter (DEU and “de”)
  BIND(<http://publications.europa.eu/resource/authority/language/DEU> AS ?language)
  
  ######################################################################
  # PART 1: Current Consolidation (law instance) – from Query 1
  ######################################################################
  ?consolidation a jolux:Consolidation .
  ?consolidation jolux:dateApplicability ?dateApplicabilityNode .
  OPTIONAL { ?consolidation jolux:dateEndApplicability ?dateEndApplicability . }
  FILTER( xsd:date(?dateApplicabilityNode) <= xsd:date(?currentDate)
          && (!BOUND(?dateEndApplicability) || xsd:date(?dateEndApplicability) >= xsd:date(?currentDate)) )
  
  ?consolidation jolux:isRealizedBy ?consoExpression .
  ?consoExpression jolux:language ?language .
  ?consoExpression jolux:isEmbodiedBy ?manifestation .
  
  # Retrieve the file URL and file format from the manifestation.
  ?manifestation jolux:isExemplifiedBy ?fileURL .
  ?manifestation jolux:userFormat/skos:notation ?fileFormatNode .
  FILTER( datatype(?fileFormatNode) = <https://fedlex.data.admin.ch/vocabulary/notation-type/uri-suffix> )
  FILTER( str(?fileFormatNode) = "html" )
  
  ######################################################################
  # PART 2: Abstract metadata – from Query 2
  ######################################################################
  # Link the consolidation to its abstract (metadata) information.
  ?consolidation jolux:isMemberOf ?consoAbstract .
  ?consoAbstract a jolux:ConsolidationAbstract .
  ?consoAbstract jolux:classifiedByTaxonomyEntry/skos:notation ?srNotation .
  FILTER( datatype(?srNotation) = <https://fedlex.data.admin.ch/vocabulary/notation-type/id-systematique> )
  
  # Validity filters at the abstract level
  OPTIONAL { ?consoAbstract jolux:dateNoLongerInForce ?ccNoLonger . }
  OPTIONAL { ?consoAbstract jolux:dateEndApplicability ?ccEnd . }
  FILTER( !BOUND(?ccNoLonger) || xsd:date(?ccNoLonger) > xsd:date(?currentDate) )
  FILTER( !BOUND(?ccEnd) || xsd:date(?ccEnd) >= xsd:date(?currentDate) )
  
  # Abstract dates and title information
  ?consoAbstract jolux:dateDocument ?dateDocumentNode .
  OPTIONAL { ?consoAbstract jolux:dateEntryInForce ?dateEntryInForceNode . }
  OPTIONAL { ?consoAbstract jolux:publicationDate ?publicationDateNode . }
  
  ?consoAbstract jolux:isRealizedBy ?consoAbstractExpression .
  ?consoAbstractExpression jolux:language ?languageConcept .
  ?consoAbstractExpression jolux:title ?title .
  OPTIONAL { ?consoAbstractExpression jolux:titleShort ?abbreviation . }
  OPTIONAL { ?consoAbstractExpression jolux:titleAlternative ?titleAlternative . }
  
  # Optionally retrieve the “aufhebungsdatum” if available.
  OPTIONAL {
    ?consoAbstract jolux:aufhebungsdatum ?aufhebungsdatum .
  }
  
  # Further validity filters on the abstract’s applicability dates
  OPTIONAL { ?consoAbstract jolux:dateEndApplicability ?ccEndDate . }
  FILTER( !BOUND(?ccEndDate) || xsd:date(?ccEndDate) >= xsd:date(?currentDate) )
  OPTIONAL { ?consoAbstract jolux:dateNoLongerInForce ?ccEndForce . }
  FILTER( !BOUND(?ccEndForce) || xsd:date(?ccEndForce) > xsd:date(?currentDate) )
  
  # Language filter on the abstract expression
  ?languageConcept skos:notation ?languageNotation .
  FILTER( datatype(?languageNotation) = <http://publications.europa.eu/ontology/euvoc#XML_LNG> )
  FILTER( str(?languageNotation) = "de" )
}
ORDER BY ?srNotation
