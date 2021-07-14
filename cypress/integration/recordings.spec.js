/**
 * Tests about hearing recording snippets.
 */
context("Recordings", function () {
  describe("On the search page", () => {
    it("should display for words", () => {
      cy.intercept("https://speech-db.altlab.app/api/bulk_search?*", {
        fixture: "recording/bulk_search/wâpamêw.json",
      }).as("bulkSearch");

      // 'wâpamêw' is the word that we have a bunch of recordings for
      cy.visitSearch("wâpamêw");
      cy.wait("@bulkSearch");

      // Play the recording:
      cy.contains(".definition-title", "wâpamêw")
        .find("button[data-cy=play-recording]")
        .click();
    });
  });

  describe("On the definition page", () => {
    beforeEach(() => {
      // Intercept calls to our API
      cy.intercept("https://speech-db.altlab.app/api/bulk_search?*", {
        fixture: "recording/bulk_search/wâpamêw.json",
      }).as("recordingsResults");
    });

    it("should play a recording via a 🔊 icon", function () {
      // Get to the definition/paradigm page for "wâpamêw"
      cy.visitLemma("wâpamêw");
      cy.wait("@recordingsResults");

      // And we should be able to click it.
      cy.get("[data-cy=play-recording]").click();

      // Note: figuring out if the audio actually played is... involved,
      // and error-prone, so it is not tested.
      // If you *want* to mock the Audio constructor... I mean, you can...
      // https://github.com/cypress-io/cypress/issues/1750#issuecomment-390751415
    });

    it("should display the lemma's multiple speakers when the speaker icon is clicked", () => {
      // 'wâpamêw' is the word that we have a bunch of recordings for
      cy.visitLemma("wâpamêw");
      cy.wait("@recordingsResults");

      // then hover/focus on the speaker icon
      cy.get("[data-cy=play-recording]")
        .focus()
        // click the icon
        .click();

      // the names of the speakers should appear on the page in a dropdown list (select tag)
      cy.get("[data-cy=multiple-recordings]").find("select");
    });

    it("should play an individual speaker's pronounciation of the word when the speaker's name is clicked", () => {
      // 'wâpamêw' is the word that we have a bunch of recordings for
      cy.visitLemma("wâpamêw");

      // then hover/focus on the speaker icon
      cy.get("[data-cy=play-recording]")
        .focus()
        // click the icon
        .click();

      // the names of the speakers should appear on the page via the select tag
      cy.get("[data-cy=multiple-recordings]").find("button");

      // clicking the 'play' button should output sound
      cy.get("[data-cy=play-selected-speaker]").click();
    });

    it("should open a link to the speaker's webpage in a new tab", () => {
      // 'wâpamêw' is the word that we have a bunch of recordings for
      cy.visitLemma("wâpamêw");

      // select the word and move to its paradigm,
      cy.get("[data-cy=definition-title]").first().click();

      // then hover/focus on the speaker icon
      cy.get("[data-cy=play-recording]")
        .focus()
        // click the icon
        .click();

      // the name of the speaker should appear as a link: clicking the link should open a new tab
      cy.get("[data-cy=learn-about-speaker]").should(
        "have.attr",
        "target",
        "_blank"
      );
    });
  });
});
