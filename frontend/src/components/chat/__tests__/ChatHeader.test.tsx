import { render, screen } from "@testing-library/react";
import { ChatHeader } from "../ChatHeader";

const reportInfo = { id: "r_msft", title: "MSFT Initiation Report" } as any;

it("shows attached-report banner with link when session is bound and report exists", () => {
  render(
    <ChatHeader
      session={{ id: "s1", attached_report_id: "r_msft" } as any}
      attachedReport={reportInfo}
      locked={false}
    />
  );
  expect(screen.getByText(/discussing report: msft initiation report/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /open report/i })).toBeInTheDocument();
});

it("shows locked banner and hides Open-report link when locked", () => {
  render(
    <ChatHeader
      session={{ id: "s1", attached_report_id: "r_msft" } as any}
      attachedReport={null}
      locked={true}
      lockMessage="The report this discussion was about can no longer be fetched. I'm unable to answer any questions about it."
    />
  );
  expect(screen.getByText(/can no longer be fetched/i)).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /open report/i })).not.toBeInTheDocument();
});

it("shows no attached-report banner when session is unbound", () => {
  render(
    <ChatHeader
      session={{ id: "s1", attached_report_id: null } as any}
      attachedReport={null}
      locked={false}
    />
  );
  expect(screen.queryByText(/discussing report/i)).not.toBeInTheDocument();
});
